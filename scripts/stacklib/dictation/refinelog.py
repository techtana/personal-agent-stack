"""The refine log: each suggestion with the text it was made from, one JSON object per line, kept for a short time
only (`refine.keep_minutes`, 30 by default) and then deleted.

    .run/dictation/refine-log.jsonl   (state_dir of the machine profile; gitignored, never sent anywhere)

Each refine adds one entry, whatever happened to the suggestion:
    {"id": "20261107-142233-a1b2", "time": "2026-11-07T14:22:33-07:00", "ts": 1794079353.2, "kind": "refine",
     "style": "polish", "style_name": "Polish", "model": "local-primary", "app": "winword.exe",
     "window": "Report.docx - Word", "before": "<the selected text>", "after": "<the model's suggestion>",
     "status": "replaced", "note": "", "seconds": 1.4}
status: replaced (pasted over the selection) | copied (left on the clipboard, nothing replaced) | rejected (the reply
failed the checks; your text stayed) | unchanged | cancelled | failed | skipped. A revert adds {"kind": "revert",
"of": <id>, "before": <the refined text that was selected>, "after": <the original put back>, ...}.

Unlike the app log (tray.log), which keeps lengths and timings only, this file holds your text, so it holds it briefly:
long enough to review a suggestion, copy it back or revert it. Entries older than keep_minutes are left out of every
read at once, and deleted from the file by prune(): when the app starts, before each new entry, and once a minute
while it runs (App._prune_logs in app.py), so a suggestion is gone from disk within a minute of expiring even
when you refine nothing else. When the last entry goes, the file goes too. The deleted text may stay in free disk
space until something overwrites it; the file is never copied anywhere.
"""
from __future__ import annotations

import difflib
import json
import os
import secrets
import threading
import time
from datetime import datetime
from pathlib import Path

LOG_NAME = "refine-log.jsonl"
KEEP_MINUTES = 30.0   # refine.keep_minutes
MATCH_AUTO = 0.9      # Revert selection: how close the selection must be to a logged suggestion
MATCH_CHOSEN = 0.8    # Revert from History, where you picked the entry yourself


def normalise(text: str) -> str:
    return " ".join((text or "").split())


def similarity(a: str, b: str) -> float:
    """1.0 for the same text up to whitespace; otherwise difflib's ratio on the normalised texts."""
    na, nb = normalise(a), normalise(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    if min(len(na), len(nb)) < 0.7 * max(len(na), len(nb)):
        return 0.0  # lengths too far apart to be the same text; skip the quadratic comparison
    return difflib.SequenceMatcher(None, na, nb, autojunk=False).ratio()


def stamp(entry: dict) -> float | None:
    """When an entry was written (seconds since the epoch): its "ts", else its ISO "time"; None when neither reads."""
    ts = entry.get("ts")
    if isinstance(ts, (int, float)) and not isinstance(ts, bool):
        return float(ts)
    try:
        return datetime.fromisoformat(str(entry.get("time"))).timestamp()
    except (TypeError, ValueError, OverflowError):
        return None


class RefineLog:
    def __init__(self, path: Path, keep_minutes: float = KEEP_MINUTES, clock=time.time) -> None:
        self.path = Path(path)
        self.keep_minutes = keep_minutes   # the app updates it when refine.keep_minutes changes
        self.clock = clock
        self._lock = threading.Lock()

    def _cutoff(self) -> float:
        return self.clock() - float(self.keep_minutes) * 60.0

    def _fresh(self, entry: dict, cutoff: float) -> bool:
        when = stamp(entry)
        return when is not None and when >= cutoff

    def append(self, entry: dict) -> dict:
        now = self.clock()
        entry = {"id": f"{time.strftime('%Y%m%d-%H%M%S', time.localtime(now))}-{secrets.token_hex(2)}",
                 "time": datetime.fromtimestamp(now).astimezone().isoformat(timespec="seconds"),
                 "ts": round(now, 3), **entry}
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        with self._lock:
            self._prune_locked()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8", newline="\n") as f:
                f.write(line)
                f.flush()
        return entry

    def entries(self, limit: int = 0) -> list[dict]:
        """Newest first, expired entries left out. A line that does not parse (a crash mid-write, a hand edit) is
        skipped, not fatal; prune() deletes it."""
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            return []
        cutoff = self._cutoff()
        out: list[dict] = []
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except ValueError:
                continue
            if isinstance(item, dict) and item.get("id") and self._fresh(item, cutoff):
                out.append(item)
                if limit and len(out) >= limit:
                    break
        return out

    def prune(self) -> int:
        """Delete expired entries, and lines that do not parse, from the file; delete the file when nothing is left.
        Returns how many lines went."""
        with self._lock:
            return self._prune_locked()

    def _prune_locked(self) -> int:
        tmp = self.path.with_name(self.path.name + ".tmp")
        try:
            tmp.unlink(missing_ok=True)   # left by a prune that was cut short; the log itself is the true copy
        except OSError:
            pass
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return 0
        except UnicodeDecodeError:
            lines = ["(unreadable)"]   # not text we wrote: drop it all
        except OSError:
            return 0                   # busy (another program reading it): the next prune tries again
        cutoff = self._cutoff()
        kept, total = [], 0
        for line in lines:
            if not line.strip():
                continue
            total += 1
            try:
                item = json.loads(line)
            except ValueError:
                continue
            if isinstance(item, dict) and self._fresh(item, cutoff):
                kept.append(line)
        removed = total - len(kept)
        if not removed:
            return 0
        for attempt in range(5):  # Windows refuses to replace a file another process has open for a moment
            try:
                if kept:
                    tmp.write_text("\n".join(kept) + "\n", encoding="utf-8", newline="\n")
                    os.replace(tmp, self.path)
                else:
                    self.path.unlink()
                return removed
            except FileNotFoundError:
                return removed
            except PermissionError:
                time.sleep(0.05 * (attempt + 1))
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return 0

    def get(self, entry_id: str) -> dict | None:
        return next((e for e in self.entries() if e.get("id") == entry_id), None)

    def reverted_ids(self, entries: list[dict] | None = None) -> set[str]:
        return {e.get("of") for e in (entries if entries is not None else self.entries()) if e.get("kind") == "revert"}

    def find(self, selected: str, threshold: float = MATCH_AUTO, scan: int = 1000) -> tuple[dict, float] | None:
        """The newest refine whose suggestion matches the selected text best, if it is close enough. Only suggestions
        that reached the document (replaced) or the clipboard (copied, which you may have pasted) count, and only
        while they are kept."""
        best: tuple[dict, float] | None = None
        for e in self.entries(scan):
            if e.get("kind") != "refine" or e.get("status") not in ("replaced", "copied") or not e.get("after"):
                continue
            score = similarity(selected, e["after"])
            if score >= 1.0:
                return e, score
            if score >= threshold and (best is None or score > best[1]):
                best = (e, score)
        return best
