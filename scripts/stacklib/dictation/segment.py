"""Turn per-frame speech probabilities into phrases and an automatic stop.

The VAD scores each 32 ms frame (512 samples at 16 kHz). The segmenter decides, frame by frame:
  - when speech starts (a run of frames above `on` lasting `min_speech_s`; shorter blips such as a click are ignored),
  - when a phrase ends (`phrase_pause_s` of quiet after speech): live mode types it, polish mode transcribes it early,
  - when to stop listening: `silence_stop_s` of quiet after you spoke, `start_timeout_s` if you never spoke, or the hard
    `max_s` limit. Hold-to-talk sessions turn the silence rules off (`auto_stop=False`): releasing the key stops them.
Pure Python, no audio here, so the timing rules are unit-tested with made-up probabilities.
"""
from __future__ import annotations

from dataclasses import dataclass

FRAME = 512
RATE = 16000
FRAME_S = FRAME / RATE


@dataclass(frozen=True)
class Event:
    kind: str          # "speech" (first speech of the session) | "phrase" | "stop"
    start: int = 0     # phrase: first frame
    end: int = 0       # phrase: one past the last speech frame
    reason: str = ""   # stop: "silence" | "no_speech" | "max_length" | what finish() was given


class Segmenter:
    def __init__(self, *, frame_s: float = FRAME_S, on: float = 0.5, off: float = 0.35, min_speech_s: float = 0.12,
                 phrase_pause_s: float = 0.7, silence_stop_s: float = 3.0, start_timeout_s: float = 8.0,
                 max_s: float = 600.0, max_phrase_s: float = 25.0, auto_stop: bool = True) -> None:
        self.frame_s = frame_s
        self.on, self.off = on, off
        self.min_frames = max(1, round(min_speech_s / frame_s))
        self.phrase_pause_s = phrase_pause_s
        self.silence_stop_s = silence_stop_s
        self.start_timeout_s = start_timeout_s
        self.max_s = max_s
        self.max_phrase_s = max_phrase_s
        self.auto_stop = auto_stop
        self.n = 0                 # frames seen
        self.run = 0               # consecutive frames >= on while not in speech
        self.in_speech = False
        self.heard = False
        self.phrase_start: int | None = None
        self.last_speech = -1      # index of the last speech frame
        self.stopped = False

    @property
    def elapsed_s(self) -> float:
        return self.n * self.frame_s

    @property
    def quiet_s(self) -> float:
        """Seconds since the last speech frame (0 before any speech or while speaking)."""
        if not self.heard or self.in_speech:
            return 0.0
        return (self.n - 1 - self.last_speech) * self.frame_s

    def push(self, prob: float) -> list[Event]:
        if self.stopped:
            return []
        events: list[Event] = []
        i = self.n
        self.n += 1
        if self.in_speech:
            if prob >= self.off:
                self.last_speech = i
            else:
                self.in_speech = False
        elif prob >= self.on:
            self.run += 1
            if self.run >= self.min_frames:
                self.in_speech = True
                self.last_speech = i
                if self.phrase_start is None:
                    self.phrase_start = i - self.run + 1
                self.run = 0
                if not self.heard:
                    self.heard = True
                    events.append(Event("speech"))
        else:
            self.run = 0
        if self.phrase_start is not None:
            if not self.in_speech and self.quiet_s >= self.phrase_pause_s:
                events.append(Event("phrase", self.phrase_start, self.last_speech + 1))
                self.phrase_start = None
            elif (i + 1 - self.phrase_start) * self.frame_s >= self.max_phrase_s:
                # Whisper reads at most 30 s at a time; cut a long run without pauses so live mode keeps typing.
                events.append(Event("phrase", self.phrase_start, i + 1))
                self.phrase_start = i + 1 if self.in_speech else None
        if self.auto_stop:
            if self.heard and self.quiet_s >= self.silence_stop_s:
                return events + self.finish("silence")
            if not self.heard and self.elapsed_s >= self.start_timeout_s:
                return events + self.finish("no_speech")
        if self.elapsed_s >= self.max_s:
            return events + self.finish("max_length")
        return events

    def finish(self, reason: str = "manual") -> list[Event]:
        """Close the open phrase (if any) and stop. Called on an automatic stop and when the user stops by hand."""
        if self.stopped:
            return []
        self.stopped = True
        events: list[Event] = []
        if self.phrase_start is not None:
            end = self.n if self.in_speech else self.last_speech + 1
            if end > self.phrase_start:
                events.append(Event("phrase", self.phrase_start, end))
            self.phrase_start = None
        if reason == "manual" and not self.heard:
            reason = "no_speech"
        events.append(Event("stop", reason=reason))
        return events
