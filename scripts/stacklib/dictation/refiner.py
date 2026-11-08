"""Refine selected text in any app, and put the original back: the flow behind the refine button and its hotkey.

    select text -> click the refine button (or press the hotkey) -> Ctrl+C -> the gateway's local model rewrites it
    in the chosen style -> the reply is checked -> Ctrl+C again: still the same selection? -> Ctrl+V over it

Every suggestion goes into the refine log (refinelog.py) with the text it came from, also when it was rejected or
not pasted, so you can read it, copy it or revert it later. Revert: select the refined text and choose Revert; the
log entry whose suggestion matches the selection gives the original, which is pasted over it.

One job at a time, on its own thread; the clipboard work runs on the inserter thread through call(). Esc belongs to
the job that grabbed it, so a cancelled job that is still waiting for the model can never take Esc away from the next
one. The owner passes in its hooks, so the tests drive this class with fakes:
    call(fn) -> fn(ws, clip) on the inserter thread      target() -> the window to act on
    ui: working/done/error/cancelled/note(title, body, hint)  cfg() -> refine.Config, re-read from the profile
    refine_fn(text, style, model=, timeout=) -> refine.Result
    esc(on) -> grab or release the Esc key (never called on the hotkey thread)
    ours(hwnd) -> True for windows of this app (a menu or the history window may be in front)
    busy_elsewhere() -> a reason the refine must wait (voice typing is listening), or ""
"""
from __future__ import annotations

import threading
from dataclasses import dataclass

from . import refine
from .refinelog import MATCH_CHOSEN, RefineLog, similarity
from .selection import Selection, SelectionError, capture, replace

PREVIEW = 260


@dataclass
class Job:
    kind: str                 # refine | revert
    target: int
    style: str = ""           # refine: style id ("" = the default)
    entry: str = ""           # revert: the log entry you picked in History ("" = find it by the selected text)
    cancelled: bool = False
    final: bool = False       # the paste has begun: too late to cancel


def preview(text: str) -> str:
    flat = " ".join((text or "").split())
    return flat if len(flat) <= PREVIEW else flat[: PREVIEW - 1] + "…"


class Refiner:
    def __init__(self, *, call, target, ui, cfg, refine_fn, log: RefineLog, esc, elevated: bool,
                 ours=lambda hwnd: False, busy_elsewhere=lambda: "", logline=lambda msg: None) -> None:
        self.call, self.target, self.ui, self.cfg = call, target, ui, cfg
        self.refine_fn, self.log, self.esc, self.elevated, self.ours = refine_fn, log, esc, elevated, ours
        self.busy_elsewhere, self.logline = busy_elsewhere, logline
        self.job: Job | None = None
        self.lock = threading.Lock()
        self.esc_lock = threading.Lock()
        self.esc_owner: Job | None = None
        self.last: dict | None = None       # the newest log entry written by this session

    @property
    def busy(self) -> bool:
        return self.job is not None

    # ---------------------------------------------------------------- triggers (any thread but the hotkey thread)

    def start(self, style: str = "", source: str = "") -> bool:
        return self._begin(Job("refine", 0, style=style), source)

    def revert(self, entry: str = "", source: str = "") -> bool:
        return self._begin(Job("revert", 0, entry=entry), source)

    def _begin(self, job: Job, source: str) -> bool:
        why = self.busy_elsewhere()
        if why:
            self.ui.note(why, "", "Try again when it is done.")
            return False
        with self.lock:
            if self.job is not None:
                self.ui.note("Still working on the last selection", "", "Esc cancels it.")
                return False
            job.target = self.target()
            self.job = job
        threading.Thread(target=self._guard, args=(job, source), name=f"dictation-{job.kind}", daemon=True).start()
        return True

    def cancel(self) -> bool:
        """Stop the current job before it pastes. Its thread may still wait for the model; it only logs then."""
        with self.lock:
            job = self.job
            if job is None or job.cancelled or job.final:
                return False
            job.cancelled = True
            self.job = None   # a new refine may start right away
        self._release_esc(job)
        self.ui.cancelled("Cancelled", "", "Nothing was replaced.")
        return True

    # ---------------------------------------------------------------- Esc, owned by one job

    def _grab_esc(self, job: Job) -> bool:
        with self.esc_lock:
            if job.cancelled:
                return False
            self.esc_owner = job
            self.esc(True)
            return True

    def _release_esc(self, job: Job) -> None:
        with self.esc_lock:
            if self.esc_owner is job:
                self.esc_owner = None
                self.esc(False)

    def _commit(self, job: Job) -> bool:
        """False when the job was cancelled; otherwise it can no longer be."""
        with self.lock:
            if job.cancelled:
                return False
            job.final = True
            return True

    # ---------------------------------------------------------------- worker

    def _guard(self, job: Job, source: str) -> None:
        try:
            (self._refine if job.kind == "refine" else self._revert)(job, source)
        except Exception as e:  # noqa: BLE001 - report in the bubble, keep the app
            self.logline(f"[refine] {job.kind} failed: {type(e).__name__}: {e}")
            if not job.cancelled:
                self.ui.error("Something went wrong", str(e), "Nothing was replaced.")
        finally:
            self._release_esc(job)
            with self.lock:
                if self.job is job:
                    self.job = None

    def _capture(self, job: Job) -> Selection | None:
        try:
            return self.call(lambda ws, clip: capture(ws, clip, job.target, elevated=self.elevated))
        except SelectionError as e:
            if not job.cancelled:
                self.ui.error(e.title, "", e.hint)
            self.logline(f"[refine] {job.kind}: no selection read ({e.title})")
            return None

    def _replace(self, sel: Selection, text: str) -> tuple[str, str]:
        return self.call(lambda ws, clip: replace(ws, clip, sel, text, ours=self.ours))

    def _refine(self, job: Job, source: str) -> None:
        cfg = self.cfg()
        style = refine.style_named(cfg, job.style)
        self.ui.working(f"Refining with {style.name}", "", "Reading the selection…")
        sel = self._capture(job)
        if sel is None or job.cancelled:
            return
        if len(sel.text) > cfg.max_chars:
            self.ui.error("The selection is too long", f"{len(sel.text):,} characters.",
                          f"Refine takes up to {cfg.max_chars:,} at a time; select a part of it.")
            return
        if not self._grab_esc(job):
            return
        self.ui.working(f"Refining with {style.name}", preview(sel.text), f"{cfg.model} is rewriting it. Esc cancels.")
        res = self.refine_fn(sel.text, style, model=cfg.model, timeout=cfg.timeout_s)
        self._release_esc(job)
        entry = {"kind": "refine", "style": style.id, "style_name": style.name, "model": cfg.model,
                 "served": res.served, "app": sel.app, "window": sel.window, "before": sel.text,
                 "after": res.text if res.ok and not res.unchanged else res.suggestion, "seconds": round(res.seconds, 2)}
        sizes = f"{len(sel.text)} -> {len(res.suggestion)} chars in {res.seconds:.2f} s"
        if job.cancelled:
            if res.suggestion:
                self.last = self.log.append({**entry, "status": "cancelled", "note": "cancelled with Esc"})
            self.logline(f"[refine] {style.id}: cancelled ({sizes})")
            return
        if not res.ok:
            status = "rejected" if res.suggestion else "failed"
            self.last = self.log.append({**entry, "status": status, "note": res.note})
            self.logline(f"[refine] {style.id}: {status}, {res.note} ({sizes})")
            title = "Kept your text" if status == "rejected" else "Could not refine the text"
            hint = ("Nothing was replaced; the suggestion is in the refine history." if status == "rejected"
                    else "Nothing was replaced.")
            self.ui.error(title, res.note[:1].upper() + res.note[1:] + ".", hint)
            return
        if res.unchanged:
            self.last = self.log.append({**entry, "status": "unchanged", "note": res.note})
            self.logline(f"[refine] {style.id}: unchanged ({sizes})")
            self.ui.done("No changes needed", preview(sel.text), f"{style.name} left the text as it is.")
            return
        if not self._commit(job):
            self.last = self.log.append({**entry, "status": "cancelled", "note": "cancelled before pasting"})
            return
        outcome, detail = self._replace(sel, res.text)
        self.last = self.log.append({**entry, "status": outcome, "note": "" if outcome == "replaced" else detail})
        self.logline(f"[refine] {style.id}: {outcome} ({sizes}) in {sel.app or 'unknown app'} via {source or '?'}")
        if outcome == "replaced":
            self.ui.done(f"Replaced with {style.name}", preview(res.text),
                         "Ctrl+Z in the app undoes it. The original is in the refine history.")
        else:
            self.ui.error("Copied to the clipboard" if outcome == "copied" else "Nothing was replaced",
                          preview(res.text), detail)

    def _revert(self, job: Job, source: str) -> None:
        self.ui.working("Putting the original back", "", "Reading the selection…")
        sel = self._capture(job)
        if sel is None or job.cancelled:
            return
        if job.entry:
            entry = self.log.get(job.entry)
            score = similarity(sel.text, (entry or {}).get("after") or "")
            if entry is None or score < MATCH_CHOSEN:
                self.ui.error("The selected text is not that suggestion", preview(sel.text),
                              "Select the text the suggestion replaced, then choose Revert again.")
                return
        else:
            found = self.log.find(sel.text)
            if found is None:
                self.ui.error("Not in the refine history", preview(sel.text),
                              "Select exactly the text that was refined. History shows recent ones and can copy "
                              "an original.")
                return
            entry, score = found
        lead, _, trail = refine.split_space(sel.text)
        _, core, _ = refine.split_space(entry.get("before") or "")
        original = lead + core + trail
        if not self._commit(job):
            return
        outcome, detail = self._replace(sel, original)
        self.last = self.log.append({"kind": "revert", "of": entry.get("id"), "style": entry.get("style"),
                                     "style_name": entry.get("style_name"), "app": sel.app, "window": sel.window,
                                     "before": sel.text, "after": original, "status": outcome,
                                     "note": "" if outcome == "replaced" else detail, "match": round(score, 3)})
        self.logline(f"[refine] revert of {entry.get('id')}: {outcome} ({len(sel.text)} -> {len(original)} chars)")
        if outcome == "replaced":
            when = str(entry.get("time") or "")[:16].replace("T", " ")
            hint = f"Undid {entry.get('style_name') or 'the refine'} from {when}."
            if score < 1.0:
                hint += " Edits you made after it were undone too; Ctrl+Z in the app brings them back."
            self.ui.done("Original put back", preview(original), hint)
        else:
            self.ui.error("Copied to the clipboard" if outcome == "copied" else "Nothing was replaced",
                          preview(original), detail)
