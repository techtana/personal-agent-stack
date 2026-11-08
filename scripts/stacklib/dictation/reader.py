"""Read selected text aloud in any app: the flow behind the speaker button and its hotkey.

    select text -> click the speaker button (or press the hotkey) -> Ctrl+C (your clipboard is put back) -> the text
    is cleaned for listening -> a voice is chosen -> the first sentence plays within about a second while the next
    ones are prepared

One reading at a time, on its own thread; the copy runs on the inserter thread through call(), in turn with
dictation's pastes and refine's copies. The hotkey again, a click on the button, or Esc (while it reads, when
read_aloud.esc_stops) stops it; the button's menu pauses and resumes. Nothing is written to disk: the last text read
stays in memory for "Read it again" until the app quits. Esc belongs to the reading that grabbed it, so a stopped
reading that is still finishing a sentence can never take Esc from the next one.

The owner passes in its hooks, so the tests drive this class with fakes:
    call(fn) -> fn(ws, clip) on the inserter thread          target() -> the window to read from
    ui: working/speaking/paused/done/error/cancelled/note(title, body, hint), progress(fraction or None)
    cfg() -> speak.Config, re-read from the profile           voices(cfg) -> the Voices available now
    ready(voice, cfg) -> False while the voice still has to load (the bubble says so)
    synth(text, voice, speed, cfg) -> tts.Audio, or raises (SpeechError and the like)
    player(on_start) -> start(), play(pcm, tag), finish(), wait(timeout), ahead(), pause(), resume(), stop()
    esc(on) -> grab or release Esc (never on the hotkey thread)     busy_elsewhere() -> a reason to wait, or ""
    record(voice, cfg, audio_s=, run_s=, load_s=, tokens=, wall_s=, stopped=, failed=) -> one usage record
    missing(cfg) -> what is not installed (read aloud's packages, Kokoro's weights), or ""
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from . import speak
from .selection import Selection, SelectionError, capture

LOOKAHEAD_S = 8.0         # prepare at most this much speech ahead of what plays: at about 3x real time the next
                          # piece is ready long before this runs out, and a stop wastes little work
SENTENCE_GAP_S = 0.05
PARAGRAPH_GAP_S = 0.35
PREVIEW = 260


def preview(text: str) -> str:
    flat = " ".join((text or "").split())
    return flat if len(flat) <= PREVIEW else flat[: PREVIEW - 1] + "…"


def silence(seconds: float, rate: int = speak.SAMPLE_RATE) -> bytes:
    return bytes(2 * int(rate * seconds))


@dataclass
class Job:
    kind: str                       # read | again | sample
    target: int = 0
    text: str | None = None         # given text (again, sample); None = read the selection
    voice: str = ""                 # sample: this voice
    cancelled: bool = False
    paused: bool = False
    player: object = None
    voice_used: speak.Voice | None = None
    note: str = ""
    pieces: list = field(default_factory=list)
    index: int = -1
    hint: str = ""


class Reader:
    def __init__(self, *, call, target, ui, cfg, voices, synth, player, esc, ready=lambda voice, cfg: True,
                 busy_elsewhere=lambda: "", record=lambda *a, **k: None, logline=lambda msg: None,
                 elevated: bool = False, hotkey_text=lambda: "", missing=lambda cfg: "") -> None:
        self.call, self.target, self.ui, self.cfg = call, target, ui, cfg
        self.voices, self.synth, self.player, self.esc, self.ready = voices, synth, player, esc, ready
        self.busy_elsewhere, self.record, self.logline = busy_elsewhere, record, logline
        self.elevated, self.hotkey_text, self.missing = elevated, hotkey_text, missing
        self.job: Job | None = None
        self.lock = threading.Lock()
        self.esc_lock = threading.Lock()
        self.esc_owner: Job | None = None
        self.last_text = ""

    @property
    def busy(self) -> bool:
        return self.job is not None

    @property
    def paused(self) -> bool:
        job = self.job
        return bool(job and job.paused)

    # ---------------------------------------------------------------- triggers (any thread but the hotkey thread)

    def start(self, source: str = "", target: int = 0) -> bool:
        """Read the selection of `target` (0 = the window in front, or the last one you used)."""
        return self._begin(Job("read", target), source)

    def again(self, source: str = "") -> bool:
        if not self.last_text:
            self.ui.note("Nothing read yet", "", "Select text and read it first.")
            return False
        return self._begin(Job("again", text=self.last_text), source)

    def sample(self, voice_id: str, name: str) -> bool:
        """A short sentence in a voice you just chose."""
        return self._begin(Job("sample", text=f"Hello, this is {name}. This is how I read your text.",
                               voice=voice_id), "sample")

    def toggle(self, source: str = "") -> bool:
        """The hotkey and a click: read when idle; stop while reading; resume when paused (a click)."""
        if self.job is not None:
            if self.job.paused and source == "button":
                return self.resume()
            return self.stop()
        return self.start(source)

    def _begin(self, job: Job, source: str) -> bool:
        why = self.busy_elsewhere()
        if why:
            self.ui.note(why, "", "Try again when it is done.")
            return False
        with self.lock:
            if self.job is not None:
                self.ui.note("Still reading", "", "Stop it first: the hotkey, a click on the button, or Esc.")
                return False
            if job.kind == "read":
                job.target = job.target or self.target()
            self.job = job
        threading.Thread(target=self._guard, args=(job, source), name="read-aloud", daemon=True).start()
        return True

    def stop(self) -> bool:
        with self.lock:
            job = self.job
            if job is None or job.cancelled:
                return False
            job.cancelled = True
            self.job = None   # a new reading may start right away
        if job.player is not None:
            job.player.stop()
        self._release_esc(job)
        self.ui.cancelled("Stopped reading", "", "")
        return True

    def pause(self) -> bool:
        job = self.job
        if job is None or job.player is None or job.paused:
            return False
        job.player.pause()
        job.paused = True
        piece = job.pieces[job.index].text if 0 <= job.index < len(job.pieces) else ""
        self.ui.paused("Paused", preview(piece), "Click the speaker button or choose Resume to go on.")
        return True

    def resume(self) -> bool:
        job = self.job
        if job is None or job.player is None or not job.paused:
            return False
        job.player.resume()
        job.paused = False
        self._show_piece(job)
        return True

    # ---------------------------------------------------------------- Esc, owned by one reading

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

    # ---------------------------------------------------------------- worker

    def _guard(self, job: Job, source: str) -> None:
        try:
            self._read(job, source)
        except Exception as e:  # noqa: BLE001 - report in the bubble, keep the app
            self.logline(f"[read] failed: {type(e).__name__}: {e}")
            if not job.cancelled:
                self.ui.error("Could not read it aloud", str(e)[:200], "")
        finally:
            self._release_esc(job)
            if job.player is not None:
                job.player.stop()
            with self.lock:
                if self.job is job:
                    self.job = None

    def _selection(self, job: Job) -> Selection | None:
        try:
            return self.call(lambda ws, clip: capture(ws, clip, job.target, elevated=self.elevated, purpose="read"))
        except SelectionError as e:
            if not job.cancelled:
                self.ui.error(e.title, "", e.hint)
            self.logline(f"[read] no selection read ({e.title})")
            return None

    def _show_piece(self, job: Job) -> None:
        n = len(job.pieces)
        i = max(0, job.index)
        title = f"Reading with {job.voice_used.name}" if job.voice_used else "Reading"
        if n > 1:
            title += f" ({i + 1} of {n})"
        body = job.pieces[i].text if i < n else ""
        self.ui.speaking(title, preview(body), job.hint)
        self.ui.progress(i / n if n else None)

    def _on_start(self, job: Job, index: object) -> None:
        if job.cancelled or not isinstance(index, int):
            return
        job.index = index
        if not job.paused:
            self._show_piece(job)

    def _hint(self, cfg: speak.Config, note: str) -> str:
        keys = [k for k in (self.hotkey_text(), "Esc" if cfg.esc_stops else "") if k]
        stop = (" or ".join(keys) + " stops; " if keys else "") + "a click on the button stops; right-click to pause."
        return (note + " " if note else "") + stop[:1].upper() + stop[1:]

    def _read(self, job: Job, source: str) -> None:
        cfg = self.cfg()
        t0 = time.monotonic()
        app = ""
        if job.text is None:
            self.ui.working("Read aloud", "", "Reading the selection…")
            sel = self._selection(job)
            if sel is None or job.cancelled:
                return
            raw, app = sel.text, sel.app
        else:
            raw = job.text
        text = speak.speech_text(raw)
        if not text:
            self.ui.error("Nothing to read", "", "The selection has no words to read.")
            return
        cut = len(text) > cfg.max_chars
        if cut:
            text = speak.cut(text, cfg.max_chars)
        if job.kind != "sample":
            self.last_text = text
        voices = self.voices(cfg)
        if job.voice:
            voice, note = speak.find_voice(job.voice, voices), ""
        else:
            voice, note = speak.pick_voice(cfg, text, voices)
        why = self.missing(cfg)
        if voice is None:
            title = "Read aloud is not installed" if why.startswith("Read aloud is not") else "No voice to read with"
            self.ui.error(title, "", why or "Add a Windows voice in Settings > Time & language > Speech.")
            return
        if why and not job.voice and voice.id != cfg.voice:
            note = f"{note} {why}".strip()   # the chosen voice is missing: say how to get it back
        if cut:
            note = (note + " " if note else "") + f"Only the first {cfg.max_chars:,} characters are read."
        job.voice_used, job.note = voice, note
        job.pieces = speak.pieces(text)
        job.hint = self._hint(cfg, note)
        if cfg.esc_stops and not self._grab_esc(job):
            return
        player = self.player(lambda tag: self._on_start(job, tag))
        try:
            player.start()
        except Exception as e:  # noqa: BLE001 - PlayerError: no output device
            self.ui.error("No sound output", str(e), "Check the speakers in Windows' sound settings.")
            return
        job.player = player
        if job.cancelled:     # stopped while the device opened
            player.stop()
            return
        audio_s = run_s = load_s = 0.0
        tokens = 0
        failed = ""
        for i, piece in enumerate(job.pieces):
            while not job.cancelled and player.ahead() > LOOKAHEAD_S:
                time.sleep(0.05)
            if job.cancelled:
                break
            if i == 0:
                loading = "" if self.ready(voice, cfg) else " Loading the voice first (a second or two)."
                self.ui.working(f"Preparing {voice.name}", preview(piece.text), (note + loading).strip())
            try:
                audio = self.synth(piece.text, voice, cfg.speed, cfg)
            except Exception as e:  # noqa: BLE001 - SpeechError, or a COM or ONNX error
                fallback = self._fallback(voice, voices) if i == 0 and voice.engine == "kokoro" else None
                if fallback is None:
                    failed = type(e).__name__
                    self.logline(f"[read] {voice.id}: {e}")
                    if not job.cancelled:
                        self.ui.error("Could not read it aloud", str(e)[:200],
                                      "Choose another voice in the button's menu." if i == 0 else "Stopped there.")
                    break
                note = f"{e}. {fallback.name} (a Windows voice) reads it instead."
                self.logline(f"[read] {voice.id} failed ({e}); falling back to {fallback.id}")
                voice = job.voice_used = fallback
                job.hint = self._hint(cfg, note)
                audio = self.synth(piece.text, voice, cfg.speed, cfg)
            audio_s += audio.seconds
            run_s += audio.run_s
            load_s += audio.load_s
            tokens += audio.tokens
            if job.cancelled:
                break
            player.play(audio.pcm + silence(PARAGRAPH_GAP_S if piece.paragraph_end else SENTENCE_GAP_S), i)
        made = time.monotonic()   # the usage record's wall clock ends here: playback is not the model's time
        player.finish()
        while not player.wait(0.2):
            if job.cancelled:
                break
        stopped = job.cancelled
        self._release_esc(job)
        if audio_s or failed:
            self.record(voice, cfg, audio_s=audio_s, run_s=run_s, load_s=load_s, tokens=tokens,
                        wall_s=made - t0, stopped=stopped, failed=failed)
        self.logline(f"[read] {job.kind} via {source or '?'}: {len(text)} chars in {len(job.pieces)} piece(s), "
                     f"{audio_s:.1f} s of speech by {voice.id} ({run_s:.2f} s to make, load {load_s:.1f} s)"
                     f"{' in ' + app if app else ''}{'; stopped' if stopped else ''}{'; ' + failed if failed else ''}")
        if stopped or failed:
            return
        self.ui.progress(None)
        if job.kind == "sample":
            self.ui.done(f"Voice: {voice.name}", voice.label, "Read aloud uses it from now on.")
        else:
            self.ui.done("Finished reading", preview(text),
                         f"{voice.name} read {speak.seconds_text(audio_s)} of speech." + (f" {note}" if note else ""))

    @staticmethod
    def _fallback(voice: speak.Voice, voices: list[speak.Voice]) -> speak.Voice | None:
        """A Windows voice for the same language when a Kokoro voice cannot speak (Kokoro failed to load)."""
        same = [v for v in voices if v.engine == "windows" and v.family == voice.family]
        return same[0] if same else None
