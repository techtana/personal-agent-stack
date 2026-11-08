"""The voice typing history: what you dictated, as Whisper heard it and as it was typed, kept for a short time only
(`dictation.keep_minutes`, 30 by default) and then deleted. Same store and the same expiry as the refine log
(refinelog.py), in its own file:

    .run/dictation/voice-history.jsonl   (state_dir of the machine profile; gitignored, never sent anywhere)

Each dictation that produced text adds one entry, whatever happened to it:
    {"id": "20261108-101530-c3d4", "time": "2026-11-08T10:15:30-07:00", "ts": 1794154530.1, "kind": "dictation",
     "mode": "polish", "style": "clean", "app": "winword.exe", "window": "Report.docx - Word",
     "before": "<the transcript as heard>", "after": "<the text typed>", "status": "inserted", "note": "",
     "seconds": 6.2}
status: inserted (typed or pasted into the app) | copied (left on the clipboard) | failed.

The History window lists the entries, and Paste last text again / Copy last text in the mic button's menu use the
newest one, so once it expires those are greyed out too. App._prune_logs deletes expired entries at start, before each
new entry and once a minute; the file goes with its last entry.
"""
from __future__ import annotations

from .refinelog import RefineLog

VOICE_LOG_NAME = "voice-history.jsonl"
KEEP_MINUTES = 30.0   # dictation.keep_minutes


class VoiceLog(RefineLog):
    def last(self) -> dict | None:
        """The newest dictation still kept that has text to paste again."""
        return next((e for e in self.entries(limit=50) if e.get("kind") == "dictation" and e.get("after")), None)
