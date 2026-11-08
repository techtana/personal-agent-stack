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
    warm(cfg) -> load the voice now (runs while the selection is copied)
    workers(voice) -> pieces to make at once; lookahead_s(voice) -> seconds of speech to keep ready ahead
    pc_busy() -> True while the processors are nearly full: then one piece at a time, one ahead

The first sentence is made on its own (falling back to a Windows voice when Kokoro cannot speak); the rest are made
by `workers` threads at once and handed to the player in order, so a long text plays without gaps.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from . import speak
from .selection import Selection, SelectionError, capture

LOOKAHEAD_S = 30.0        # prepare at most this much speech ahead of what plays (the owner's hooks may say more)
SENTENCE_GAP_S = 0.05
PARAGRAPH_GAP_S = 0.35
PREVIEW = 260


KEEP_AUDIO_BYTES = 64 << 20   # Read it again keeps up to about 23 minutes of the last reading's speech in memory


@dataclass
class Replayed:
    """Audio kept from the last reading: no model time, no tokens."""
    pcm: bytes
    seconds: float
    tokens: int = 0
    run_s: float = 0.0
    load_s: float = 0.0


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
    reuse: dict = field(default_factory=dict)   # again: piece index -> audio kept from the last reading
    made: dict = field(default_factory=dict)    # piece index -> audio made (or reused) in this reading


class Reader:
    def __init__(self, *, call, target, ui, cfg, voices, synth, player, esc, ready=lambda voice, cfg: True,
                 busy_elsewhere=lambda: "", record=lambda *a, **k: None, logline=lambda msg: None,
                 elevated: bool = False, hotkey_text=lambda: "", missing=lambda cfg: "", warm=lambda cfg: None,
                 workers=lambda voice: 1, lookahead_s=lambda voice: LOOKAHEAD_S, pc_busy=lambda: False) -> None:
        self.call, self.target, self.ui, self.cfg = call, target, ui, cfg
        self.voices, self.synth, self.player, self.esc, self.ready = voices, synth, player, esc, ready
        self.busy_elsewhere, self.record, self.logline = busy_elsewhere, record, logline
        self.elevated, self.hotkey_text, self.missing = elevated, hotkey_text, missing
        self.warm, self.workers, self.lookahead_s, self.pc_busy = warm, workers, lookahead_s, pc_busy
        self.job: Job | None = None
        self.lock = threading.Lock()
        self.esc_lock = threading.Lock()
        self.esc_owner: Job | None = None
        self.last_text = ""
        self.last_audio: tuple | None = None      # (key, {piece index: audio}) of the last reading, in memory only

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
        # Load the voice while the selection is copied, so the two waits overlap.
        threading.Thread(target=self.warm, args=(cfg,), name="read-aloud-warm", daemon=True).start()
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
        stats = {"audio_s": 0.0, "run_s": 0.0, "load_s": 0.0, "tokens": 0, "played_s": 0.0}
        key = self._audio_key(text, voice, cfg)
        if job.kind == "again" and self.last_audio and self.last_audio[0] == key:
            job.reuse = dict(self.last_audio[1])     # same text, voice and speed: replay, make only what is missing
        failed = ""
        first = job.pieces[0]
        loading = "" if self.ready(voice, cfg) else " Loading the voice first (a second or two)."
        self.ui.working(f"Preparing {voice.name}", preview(first.text), (note + loading).strip())
        try:
            audio = self._make(job, 0, voice, cfg)
        except Exception as e:  # noqa: BLE001 - SpeechError, or a COM or ONNX error
            fallback = self._fallback(voice, voices) if voice.engine == "kokoro" else None
            if fallback is None:
                audio, failed = None, type(e).__name__
                self.logline(f"[read] {voice.id}: {e}")
                if not job.cancelled:
                    self.ui.error("Could not read it aloud", str(e)[:200], "Choose another voice in the button's menu.")
            else:
                note = f"{e}. {fallback.name} (a Windows voice) reads it instead."
                self.logline(f"[read] {voice.id} failed ({e}); falling back to {fallback.id}")
                voice = job.voice_used = fallback
                job.hint = self._hint(cfg, note)
                job.reuse.clear()                 # kept audio was another voice's
                audio = self._make(job, 0, voice, cfg)
        if audio is not None and not job.cancelled:
            self._add(stats, audio)
            player.play(audio.pcm + silence(PARAGRAPH_GAP_S if first.paragraph_end else SENTENCE_GAP_S), 0)
            failed = self._prefetch(job, voice, cfg, player, stats)
        audio_s, run_s, load_s, tokens = stats["audio_s"], stats["run_s"], stats["load_s"], stats["tokens"]
        if job.kind != "sample":
            self._keep_audio(job, voice, cfg)
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
                         f"{voice.name} read {speak.seconds_text(stats['played_s'])} of speech"
                         + (" (replayed: nothing was made again)." if job.reuse and not audio_s else ".")
                         + (f" {note}" if note else ""))

    @staticmethod
    def _audio_key(text: str, voice: speak.Voice, cfg: speak.Config) -> tuple:
        return text, voice.id, cfg.speed, cfg.kokoro

    def _make(self, job: Job, i: int, voice: speak.Voice, cfg: speak.Config):
        """Piece i's audio: kept from the last reading (Read it again, same voice and speed), else made now."""
        kept = job.reuse.get(i)
        if kept is not None:
            audio = Replayed(kept.pcm, kept.seconds)
        else:
            audio = self.synth(job.pieces[i].text, voice, cfg.speed, cfg)
        job.made[i] = audio
        return audio

    def _keep_audio(self, job: Job, voice: speak.Voice, cfg: speak.Config) -> None:
        """Keep this reading's audio in memory for Read it again (up to KEEP_AUDIO_BYTES; longer readings are kept
        from the start). Nothing goes to disk; the next reading of other text replaces it."""
        kept, size = {}, 0
        for i in sorted(job.made):
            size += len(job.made[i].pcm)
            if size > KEEP_AUDIO_BYTES:
                break
            kept[i] = job.made[i]
        text = self.last_text
        self.last_audio = (self._audio_key(text, voice, cfg), kept) if kept else None

    @staticmethod
    def _add(stats: dict, audio) -> None:
        stats["played_s"] += audio.seconds
        if isinstance(audio, Replayed):
            return                                   # no model ran for it
        stats["audio_s"] += audio.seconds
        stats["run_s"] += audio.run_s
        stats["load_s"] += audio.load_s
        stats["tokens"] += audio.tokens

    def _prefetch(self, job: Job, voice: speak.Voice, cfg: speak.Config, player, stats: dict) -> str:
        """Make pieces 1.. with `workers(voice)` threads at once and hand them to the player in order, while the
        speech made but not yet played stays under `lookahead_s(voice)`. While the PC is busy (`pc_busy()`, the
        processors more than 85% in use) only one piece is made at a time and at most one waits ahead, so read aloud
        never takes the processors from whatever else runs. Returns the error type when a piece failed, else ""."""
        n = len(job.pieces)
        if n < 2:
            return ""
        cond = threading.Condition()
        made: dict[int, object] = {}      # piece index -> Audio, or the exception it raised
        state = {"next": 1, "played": 1, "making": 0, "stop": False}
        workers = max(1, self.workers(voice))
        ahead_limit = self.lookahead_s(voice)

        def ahead() -> float:
            return player.ahead() + sum(a.seconds for a in made.values() if not isinstance(a, BaseException))

        def may_start() -> bool:
            if self.pc_busy():
                return state["making"] == 0 and state["next"] - state["played"] < 2
            return state["making"] < workers and ahead() < ahead_limit

        def work() -> None:
            while True:
                with cond:
                    while not job.cancelled and not state["stop"] and state["next"] < n and not may_start():
                        cond.wait(0.1)
                    if job.cancelled or state["stop"] or state["next"] >= n:
                        return
                    i = state["next"]
                    state["next"] += 1
                    state["making"] += 1
                try:
                    result = self._make(job, i, voice, cfg)
                except Exception as e:  # noqa: BLE001 - handed to the player loop, which stops there
                    result = e
                with cond:
                    made[i] = result
                    state["making"] -= 1
                    cond.notify_all()
                if isinstance(result, BaseException):
                    return

        threads = [threading.Thread(target=work, name=f"read-aloud-make-{k}", daemon=True) for k in range(workers)]
        for t in threads:
            t.start()
        failed = ""
        while state["played"] < n and not job.cancelled:
            i = state["played"]
            with cond:
                while i not in made and not job.cancelled:
                    cond.wait(0.1)
                    if not any(t.is_alive() for t in threads) and i not in made:
                        break                      # every worker ended (an error earlier): nothing more comes
                result = made.pop(i, None)
            if job.cancelled or result is None:
                break
            if isinstance(result, BaseException):
                failed = type(result).__name__
                self.logline(f"[read] {voice.id}, piece {i + 1}: {result}")
                self.ui.error("Could not read it aloud", str(result)[:200], "Stopped there.")
                break
            self._add(stats, result)
            piece = job.pieces[i]
            player.play(result.pcm + silence(PARAGRAPH_GAP_S if piece.paragraph_end else SENTENCE_GAP_S), i)
            with cond:
                state["played"] += 1
                cond.notify_all()
        with cond:
            state["stop"] = True     # an error or a stop: the workers make nothing more
            cond.notify_all()
        return failed

    @staticmethod
    def _fallback(voice: speak.Voice, voices: list[speak.Voice]) -> speak.Voice | None:
        """A Windows voice for the same language when a Kokoro voice cannot speak (Kokoro failed to load)."""
        same = [v for v in voices if v.engine == "windows" and v.family == voice.family]
        return same[0] if same else None
