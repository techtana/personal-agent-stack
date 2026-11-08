"""The refine log: every suggestion with the text it was made from, one JSON object per line, kept until you delete it.

    .run/dictation/refine-log.jsonl   (state_dir of the machine profile; gitignored, never sent anywhere)

Each refine adds one entry, whatever happened to the suggestion:
    {"id": "20261107-142233-a1b2", "time": "2026-11-07T14:22:33-07:00", "kind": "refine", "style": "polish",
     "style_name": "Polish", "model": "local-primary", "app": "winword.exe", "window": "Report.docx - Word",
     "before": "<the selected text>", "after": "<the model's suggestion>", "status": "replaced", "note": "",
     "seconds": 1.4}
status: replaced (pasted over the selection) | copied (left on the clipboard, nothing replaced) | rejected (the reply
failed the checks; your text stayed) | unchanged | cancelled | failed. A revert adds {"kind": "revert", "of": <id>,
"before": <the refined text that was selected>, "after": <the original put back>, ...}.

Unlike the voice typing log, which keeps lengths and timings only, this file holds your text: that is its purpose
(review, copy back, revert). It stays on this machine.
"""
from __future__ import annotations

import difflib
import json
import secrets
import threading
import time
from datetime import datetime
from pathlib import Path

LOG_NAME = "refine-log.jsonl"
MATCH_AUTO = 0.9      # Revert selection: how close the selection must be to a logged suggestion
MATCH_CHOSEN = 0.8    # Revert from History, where you picked the entry yourself


def normalise(text: str) -> str:
    return " ".join((text or "").split())


def revertable_in_app(entry: dict) -> bool:
    """A refine whose original Revert may paste over a selection in any app. Entries from an app plugin (the Logseq
    plugin, `source: plugin`) are undone by that plugin, block by block: any program with the plugin's key can add
    such entries, so their text is never pasted into another app."""
    return (entry.get("kind") == "refine" and entry.get("status") in ("replaced", "copied") and bool(entry.get("after"))
            and entry.get("source") != "plugin")


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


class RefineLog:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def append(self, entry: dict) -> dict:
        entry = {"id": f"{time.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(2)}",
                 "time": datetime.now().astimezone().isoformat(timespec="seconds"), **entry}
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8", newline="\n") as f:
                f.write(line)
                f.flush()
        return entry

    def entries(self, limit: int = 0) -> list[dict]:
        """Newest first. A line that does not parse (a crash mid-write, a hand edit) is skipped, not fatal."""
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            return []
        out: list[dict] = []
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except ValueError:
                continue
            if isinstance(item, dict) and item.get("id"):
                out.append(item)
                if limit and len(out) >= limit:
                    break
        return out

    def get(self, entry_id: str) -> dict | None:
        return next((e for e in self.entries() if e.get("id") == entry_id), None)

    def reverted_ids(self, entries: list[dict] | None = None) -> set[str]:
        return {e.get("of") for e in (entries if entries is not None else self.entries()) if e.get("kind") == "revert"}

    def find(self, selected: str, threshold: float = MATCH_AUTO, scan: int = 1000) -> tuple[dict, float] | None:
        """The newest refine whose suggestion matches the selected text best, if it is close enough. Only suggestions
        that reached the document (replaced) or the clipboard (copied, which you may have pasted) count."""
        best: tuple[dict, float] | None = None
        for e in self.entries(scan):
            if not revertable_in_app(e):
                continue
            score = similarity(selected, e["after"])
            if score >= 1.0:
                return e, score
            if score >= threshold and (best is None or score > best[1]):
                best = (e, score)
        return best
