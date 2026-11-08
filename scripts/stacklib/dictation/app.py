"""The voice typing app: hotkey or button -> microphone -> VAD -> Whisper -> optional cleanup -> the focused window.

Threads: Tk main loop (button, bubble); hotkeys (Win32 message loop); microphone (WinMM) which also runs the VAD and
the segmenter on each 32 ms frame; control (start, stop, cancel, in order); worker (Whisper and the cleanup, one job
at a time); inserter (clipboard and keystrokes, in order); the local HTTP control endpoint.

One pipeline serves both modes. Each phrase is transcribed as soon as you pause, with the text so far as Whisper's
prompt. Live mode types each phrase right away; polish mode joins them when you stop and asks the gateway's local model
to clean them up, so the wait after you finish is one short phrase plus the cleanup (about a second on the GPU).
"""
from __future__ import annotations

import os
import queue
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field

import numpy as np

from .. import env_value
from .. import profile as prof
from . import Config, cleanup, control, hotkey, read_state, save_setting, transcriptions, write_state
from . import api_key as transcription_key
from .audio import RATE, Recorder, RecorderError
from .engine import Engine
from .segment import FRAME, Event, Segmenter
from .textops import joiner, strip_fillers
from .vad import level, make_vad

PRE_PAD = int(0.30 * RATE)    # audio kept before the VAD's speech onset (it reacts a little late)
POST_PAD = int(0.25 * RATE)
PTT_HOLD_S = 0.35             # holding the hotkey longer than this means hold-to-talk
RESTORE_AFTER_S = 1.0         # wait before putting the previous clipboard back after a paste
MIC_SILENT_S = 4.0            # no audio buffers for this long (microphone unplugged): stop the session


def log(msg: str) -> None:
    stream = sys.stdout or sys.stderr
    if stream:
        print(f"{time.strftime('%H:%M:%S')} {msg}", file=stream, flush=True)


@dataclass
class Session:
    id: int
    mode: str
    style: str
    target: int
    app: str
    seg: Segmenter
    started: float = field(default_factory=time.monotonic)
    pcm: bytearray = field(default_factory=bytearray)     # everything recorded, int16 mono 16 kHz
    buf: bytearray = field(default_factory=bytearray)     # bytes not yet a whole VAD frame
    phrases: list[str] = field(default_factory=list)
    typed: str = ""
    language: str = ""
    ptt: bool = False
    stopping: bool = False
    cancelled: bool = False
    stop_reason: str = ""
    loud: bool = False             # any non-zero sample yet (all zeros = muted or blocked microphone)
    interim_busy: bool = False
    last_interim: float = 0.0
    last_level: float = 0.0
    transcribe_s: float = 0.0
    jobs: list = field(default_factory=list)       # live mode: InsertJobs in order
    held: str = ""                                 # live mode while the hotkey is held: typed on release
    last_audio: float = field(default_factory=time.monotonic)


@dataclass
class InsertJob:
    text: str
    method: str
    target: int
    done: threading.Event = field(default_factory=threading.Event)
    outcome: str = ""      # inserted | copied | failed | empty
    detail: str = ""


class Inserter(threading.Thread):
    """Puts text into the focused window, one job at a time, on the thread that owns the clipboard window."""

    def __init__(self, own_windows) -> None:
        super().__init__(name="dictation-insert", daemon=True)
        self.q: queue.Queue = queue.Queue()
        self.own_windows = own_windows   # callable -> set of our HWNDs

    def submit(self, job: InsertJob) -> InsertJob:
        self.q.put(job)
        return job

    def run(self) -> None:
        from . import winsys

        self.winsys = winsys
        self.clip = winsys.Clipboard()
        self.elevated = winsys.self_elevated()
        while True:
            job = self.q.get()
            if job is None:
                break
            try:
                job.outcome, job.detail = self._insert(job)
            except Exception as e:  # noqa: BLE001 - report in the bubble, keep the thread
                job.outcome, job.detail = "failed", str(e)
            job.done.set()
        self.clip.close()

    def _copy(self, text: str, why: str) -> tuple[str, str]:
        self.clip.set_text(text, hide=False)  # you will paste it yourself, so let clipboard history keep it
        return "copied", why

    def _insert(self, job: InsertJob) -> tuple[str, str]:
        ws = self.winsys
        if not job.text:
            return "empty", ""
        if job.method == "copy":
            return self._copy(job.text, "Copied.")
        if not ws.wait_modifiers_released(2.0):
            # Ctrl or Alt still held (hold-to-talk): Ctrl+V would arrive as Ctrl+Alt+V and typed letters as Alt+key.
            return self._copy(job.text, "Keys were still held down, so the text went to the clipboard: press Ctrl+V.")
        fg = ws.root_window(ws.foreground())
        if fg in self.own_windows() and job.target:
            ws.activate(job.target)  # a menu of ours took the focus; hand it back first
            time.sleep(0.1)
            fg = ws.root_window(ws.foreground())
            if fg in self.own_windows():
                fg = job.target
        if not fg or (job.target and fg != job.target):
            return self._copy(job.text, "You switched windows, so the text went to the clipboard: press Ctrl+V.")
        pid = ws.window_pid(fg)
        app = ws.process_name(pid)
        if not self.elevated and ws.is_elevated(pid) is not False:
            # True, or None: Windows would not let us read its token, which usually means it is elevated. Input sent
            # there is dropped without an error (UIPI), so never report it as typed.
            return self._copy(job.text, f"{app or 'That window'} may run as administrator, which blocks typed input. "
                                        "The text is on the clipboard: press Ctrl+V.")
        method = job.method
        snap = None
        if method == "paste":
            try:
                snap = self.clip.snapshot()
            except OSError:
                snap = None
            if snap is None:
                method = "type"  # the clipboard is busy or huge: type rather than lose its content
        if method == "paste":
            seq = self.clip.set_text(job.text)
            ok = ws.send_paste(shift_insert=app in ws.SHIFT_INSERT_APPS)
            # The target reads the clipboard while it handles Ctrl+V; a busy Electron or browser window can take a
            # while, so wait a full second, and longer while some window has the clipboard open.
            time.sleep(RESTORE_AFTER_S)
            deadline = time.monotonic() + 1.0
            while ws.clipboard_busy() and time.monotonic() < deadline:
                time.sleep(0.05)
            if ws.sequence() == seq:
                self.clip.restore(snap)
        else:
            ok = ws.type_text(job.text)
        if not ok:
            return self._copy(job.text, "Windows refused the simulated keys; the text is on the clipboard.")
        return "inserted", f"{len(job.text)} characters by {method} into {app or 'the window'}"


class App:
    def __init__(self, profile: dict) -> None:
        from . import winsys
        from .overlay import Overlay

        self.ws = winsys
        self.profile = profile
        self.cfg = Config.from_profile(profile)
        self.port = int(profile["ports"]["dictation"])
        self.gateway = f"http://127.0.0.1:{profile['ports']['litellm']}"
        self.api_key = env_value("LITELLM_MASTER_KEY")
        self.engine = Engine(self.cfg, log)
        self.vad = make_vad(log)
        self.state = "idle"               # idle | listening | finishing
        self.session: Session | None = None
        self.recorder: Recorder | None = None
        self.history: deque = deque(maxlen=10)   # (raw transcript, typed text)
        self.counter = 0
        self.commands: queue.Queue = queue.Queue()
        self.jobs: queue.Queue = queue.Queue()
        self.hotkey_vk = 0
        self.hotkey_error = ""
        self.last_target = 0
        self.last_external = 0            # last foreground window that is not ours (see _track_focus)
        # Raises when another copy runs. Also serves Open WebUI's microphone (transcriptions.py) on the same Whisper,
        # for callers with DICTATION_BEARER, looked up on each request so a key added to .env later works at once.
        self.server = control.ControlServer(
            self.port, self.health, self.act, api_key=transcription_key, log=log,
            transcribe=lambda data, **kw: transcriptions.transcribe_with(self.engine, data, **kw))
        state = read_state(profile)
        pos = (int(state["x"]), int(state["y"])) if "x" in state and "y" in state else None
        winsys.set_dpi_aware()
        self.overlay = Overlay(self, self.cfg.button, pos)
        self.inserter = Inserter(self.overlay.windows)
        self.hotkeys = winsys.HotkeyThread(self._on_hotkey)

    # ---------------------------------------------------------------- lifecycle

    def run(self) -> int:
        self.server.start()
        self.inserter.start()
        self.hotkeys.start()
        self._register_hotkey()
        threading.Thread(target=self._command_loop, name="dictation-control-loop", daemon=True).start()
        threading.Thread(target=self._worker_loop, name="dictation-worker", daemon=True).start()
        threading.Thread(target=self._track_focus, name="dictation-focus", daemon=True).start()
        self.engine.load_async()
        log(f"[dictation] ready: hotkey {self.hotkey_text()}, mode {self.cfg.mode}, cleanup {self.cfg.style} "
            f"({self.prompt_kind()} prompt), VAD {self.vad.name}, control http://127.0.0.1:{self.port}")
        if self.hotkey_error:
            self.ui(lambda: self.overlay.set_state("error", "Hotkey not available", self.hotkey_error,
                                                   "Pick another one in the tray's Settings tab; the button still works.",
                                                   hide_after=12))
        self.overlay.run()
        self.hotkeys.stop()
        self.server.stop()
        return 0

    def ui(self, fn) -> None:
        self.overlay.post(fn)

    def _track_focus(self) -> None:
        """Remember the last window you used that is not the button, so a click on the button (should it ever take
        the focus) still dictates into the app you came from."""
        while True:
            hwnd = self.ws.root_window(self.ws.foreground())
            if hwnd and hwnd not in self.overlay.windows():
                self.last_external = hwnd
            time.sleep(0.25)

    def _register_hotkey(self) -> None:
        try:
            mods, vk = hotkey.parse(self.cfg.hotkey)
        except hotkey.HotkeyError as e:
            self.hotkey_error = f"{self.cfg.hotkey}: {e}"
            return
        ok, err = self.hotkeys.register("dictate", mods, vk)
        if ok:
            self.hotkey_vk = vk
        else:
            self.hotkey_error = f"{self.hotkey_text()} is taken by another program ({err})."
            log(f"[dictation] {self.hotkey_error}")

    def hotkey_text(self) -> str:
        return hotkey.label(self.cfg.hotkey)

    def summary(self) -> str:
        mode = "types when you finish, cleaned up" if self.cfg.mode == "polish" else "types as you speak"
        style = cleanup.STYLE_NAMES.get(self.cfg.style, self.cfg.style).lower()
        engine = {"ready": f"{self.engine.model_name} on {'the GPU' if self.engine.device == 'cuda' else 'the CPU'}",
                  "loading": "loading Whisper", "unloaded": "Whisper loads on first use",
                  "failed": "Whisper failed to load"}.get(self.engine.state, self.engine.state)
        return f"Mode: {mode}" + (f" ({style})" if self.cfg.mode == "polish" else "") + f". {engine.capitalize()}."

    def health(self) -> dict:
        return {"ok": True, "state": self.state, "engine": self.engine.state, "device": self.engine.device,
                "model": self.engine.model_name, "note": self.engine.note, "vad": self.vad.name,
                "hotkey": self.cfg.hotkey, "hotkey_ok": not self.hotkey_error, "mode": self.cfg.mode,
                "style": self.cfg.style, "language": self.cfg.language, "button": bool(self.cfg.button),
                "transcriptions": bool(transcription_key()),  # Open WebUI's microphone needs DICTATION_BEARER
                "pid": os.getpid()}

    def act(self, name: str) -> dict:
        if name == "toggle":
            self.toggle("http")
        elif name == "start":
            self.commands.put(("start", "http"))
        elif name in ("stop", "cancel"):
            self.commands.put((name, "http"))
        elif name in ("show", "hide"):
            visible = name == "show"
            self.cfg.button = visible  # reported by /health at once; the Tk thread shows or hides and saves it
            self.ui(lambda: self.set_option("button", visible))
        elif name == "quit":
            self.quit()
        elif name == "reload":
            self.reload()
        return {"ok": True, "state": self.state}

    def prompt_kind(self) -> str:
        return "custom" if self.cfg.cleanup_prompt else "built-in"

    def reload(self) -> None:
        """Take the settings that need no restart from the machine file: the cleanup prompt (the tray's Apply calls
        this after saving it). The next cleanup uses it."""
        fresh = Config.from_profile(prof.resolve_profile(self.profile.get("name") or None))
        self.cfg.cleanup_prompt = fresh.cleanup_prompt
        log(f"[dictation] settings reloaded: {self.prompt_kind()} cleanup prompt")

    def quit(self) -> None:
        log("[dictation] quitting")
        self.ui(self.overlay.quit)

    # ---------------------------------------------------------------- triggers

    def toggle(self, source: str) -> None:
        if self.state == "idle":
            self.commands.put(("start", source))
        elif self.state == "listening":
            self.commands.put(("stop", source))
        else:
            self.ui(lambda: self.overlay.show_bubble("Still finishing the last one", "", "One moment.",
                                                     ink="#8cc8ff", owner="working"))

    def _on_hotkey(self, name: str) -> None:
        if name == "cancel":
            self.commands.put(("cancel", "esc"))
            return
        if self.state == "idle":
            self.commands.put(("start", "hotkey"))
            threading.Thread(target=self._watch_hold, name="dictation-ptt", daemon=True).start()
        else:
            self.toggle("hotkey")

    def _watch_hold(self) -> None:
        """Tap = listen until you stop talking. Hold = talk while held; releasing stops."""
        t0 = time.monotonic()
        while self.ws.key_down(self.hotkey_vk):
            if time.monotonic() - t0 >= PTT_HOLD_S:
                s = self.session
                while s is None and self.ws.key_down(self.hotkey_vk) and time.monotonic() - t0 < 2.0:
                    time.sleep(0.02)  # the microphone is still opening
                    s = self.session
                if s is None or s.stopping:
                    return
                s.ptt = True
                s.seg.auto_stop = False
                self.ui(lambda: self.overlay.show_bubble("Listening (hold)", self._live_text(s),
                                                         "Release the keys to finish.", ink="#ff9a8f",
                                                         owner="listening"))
                while self.ws.key_down(self.hotkey_vk):
                    time.sleep(0.02)
                if self.session is s and not s.stopping:
                    self.commands.put(("stop", "released"))
                return
            time.sleep(0.02)

    def _command_loop(self) -> None:
        while True:
            try:
                cmd, source = self.commands.get(timeout=1.0)
            except queue.Empty:
                self._watchdog()
                continue
            try:
                if cmd == "start":
                    self._start(source)
                elif cmd == "stop":
                    self._stop(source)
                elif cmd == "cancel":
                    self._cancel()
            except Exception as e:  # noqa: BLE001
                log(f"[dictation] {cmd} failed: {e}")
                self.ui(lambda e=e: self.overlay.set_state("error", "Something went wrong", str(e), hide_after=8))
                self._reset()

    def _watchdog(self) -> None:
        """Stop a session whose microphone stopped delivering audio (unplugged): the segmenter counts audio frames,
        so without buffers it would wait forever."""
        s = self.session
        if s is None or self.state != "listening" or s.stopping:
            return
        if time.monotonic() - s.last_audio > MIC_SILENT_S:
            log(f"[dictation] session {s.id}: no audio from the microphone for {MIC_SILENT_S:g} s; stopping")
            self._stop("mic_lost")
            self.ui(lambda: self.overlay.show_bubble("The microphone stopped sending audio",
                                                     "Was it unplugged? What was heard so far is being typed.",
                                                     ink="#ff9a8f", owner="working"))

    def _reset(self) -> None:
        """After an unexpected error: close the microphone, give Esc back, forget the session."""
        s = self.session
        if s is not None:
            s.cancelled = s.stopping = True
        if self.recorder:
            try:
                self.recorder.stop()
            except Exception:  # noqa: BLE001
                pass
            self.recorder = None
        self.hotkeys.unregister("cancel")
        self.session, self.state = None, "idle"

    # ---------------------------------------------------------------- session

    def _start(self, source: str) -> None:
        if self.state != "idle":
            return
        target = self.ws.root_window(self.ws.foreground())
        if not target or target in self.overlay.windows():
            target = self.last_external
        app = self.ws.process_name(self.ws.window_pid(target)) if target else ""
        cfg = self.cfg
        self.counter += 1
        seg = Segmenter(phrase_pause_s=cfg.phrase_pause_s, silence_stop_s=cfg.silence_stop_s,
                        start_timeout_s=cfg.start_timeout_s, max_s=cfg.max_minutes * 60)
        s = Session(self.counter, cfg.mode, cfg.style, target, app, seg)
        self.last_target = target or self.last_target
        self.vad.reset()
        self.engine.load_async()
        self.session = s
        self.state = "listening"
        try:
            self.recorder = Recorder(self._on_audio, cfg.mic)
            self.recorder.start()
        except RecorderError as e:
            self.session, self.state = None, "idle"
            self.ui(lambda: self.overlay.set_state("error", "Microphone not available", str(e),
                                                   "Check Settings > Privacy & security > Microphone.", hide_after=10))
            return
        self.hotkeys.register("cancel", 0, hotkey.VK_ESCAPE)
        hint = f"Stops after {cfg.silence_stop_s:g} s of quiet. {self.hotkey_text()} stops now, Esc cancels."
        loading = "" if self.engine.state == "ready" else "Loading Whisper; keep talking."
        self.ui(lambda: self.overlay.set_state("listening", "Listening", loading, hint))
        log(f"[dictation] session {s.id}: listening ({source}, {s.mode}/{s.style}) for {app or 'unknown window'}")

    def _on_audio(self, data: bytes) -> None:
        """Microphone thread: VAD and segmenter for each whole 32 ms frame."""
        s = self.session
        if s is None or s.stopping:
            return
        s.last_audio = time.monotonic()
        s.pcm += data
        s.buf += data
        frame_bytes = FRAME * 2
        while len(s.buf) >= frame_bytes:
            chunk = bytes(s.buf[:frame_bytes])
            del s.buf[:frame_bytes]
            frame = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
            if not s.loud and np.any(frame):
                s.loud = True
            events = s.seg.push(self.vad(frame))
            now = time.monotonic()
            if now - s.last_level > 0.05:
                s.last_level = now
                lvl = level(frame)
                self.ui(lambda v=lvl: self.overlay.set_level(v))
            for ev in events:
                self._on_event(s, ev)
            if s.stopping:
                return
        if not s.loud and time.monotonic() - s.started > 2.0:
            s.loud = True  # warn once
            self.ui(lambda: self.overlay.show_bubble(
                "The microphone sends silence", "Is it muted, or is microphone access off for desktop apps?",
                "Settings > Privacy & security > Microphone", ink="#ff9a8f", owner="listening"))
        self._maybe_interim(s)

    def _on_event(self, s: Session, ev: Event) -> None:
        if ev.kind == "phrase":
            self.jobs.put(("phrase", s, ev.start, ev.end))
        elif ev.kind == "stop":
            s.stopping = True
            self.commands.put(("stop", ev.reason))

    def _maybe_interim(self, s: Session) -> None:
        """While you speak, show Whisper's guess for the current phrase (GPU only; it is not typed)."""
        start = s.seg.phrase_start
        if (start is None or s.interim_busy or self.engine.state != "ready" or self.engine.device != "cuda"
                or not self.jobs.empty()):
            return
        now = time.monotonic()
        if now - s.last_interim < 0.7 or (s.seg.n - start) * FRAME < 0.6 * RATE:
            return
        s.interim_busy, s.last_interim = True, now
        self.jobs.put(("interim", s, start, len(s.pcm) // 2))

    def _stop(self, reason: str) -> None:
        s = self.session
        if s is None or self.state != "listening":
            return
        s.stopping = True
        s.stop_reason = reason
        self.state = "finishing"
        if self.recorder:
            self.recorder.stop()
            self.recorder = None
        self.hotkeys.unregister("cancel")
        for ev in s.seg.finish(reason if reason in ("silence", "no_speech", "max_length") else "manual"):
            if ev.kind == "phrase":
                self.jobs.put(("phrase", s, ev.start, ev.end))
            elif ev.kind == "stop":
                s.stop_reason = ev.reason
        if s.seg.heard:
            title = "Transcribing" if s.mode == "live" or s.style == "verbatim" else "Transcribing, then cleaning up"
            self.ui(lambda: self.overlay.set_state("working", title, self._live_text(s)))
        self.jobs.put(("finalize", s))
        log(f"[dictation] session {s.id}: stopped ({reason}) after {len(s.pcm) / 2 / RATE:.1f} s")

    def _cancel(self) -> None:
        s = self.session
        if s is None:
            return
        s.cancelled = s.stopping = True
        if self.recorder:
            self.recorder.stop()
            self.recorder = None
        self.hotkeys.unregister("cancel")
        self.session, self.state = None, "idle"
        kept = " Phrases already typed stay." if s.typed else ""
        self.ui(lambda: self.overlay.set_state("idle", "Cancelled", "", f"Nothing more will be typed.{kept}",
                                               hide_after=2.5))
        log(f"[dictation] session {s.id}: cancelled")

    # ---------------------------------------------------------------- worker

    def _worker_loop(self) -> None:
        while True:
            try:
                job = self.jobs.get(timeout=30)
            except queue.Empty:
                self.engine.unload_if_idle()
                continue
            kind, s = job[0], job[1]
            try:
                if kind == "phrase":
                    self._phrase(s, job[2], job[3])
                elif kind == "interim":
                    self._interim(s, job[2], job[3])
                elif kind == "finalize":
                    self._finalize(s)
            except Exception as e:  # noqa: BLE001
                log(f"[dictation] {kind} failed: {e}")
                if kind == "finalize" or not s.cancelled:
                    self.ui(lambda e=e: self.overlay.set_state("error", "Transcription failed", str(e), hide_after=10))
                if kind == "finalize":
                    self._idle(s)

    def _audio(self, s: Session, start_frame: int, end_sample: int) -> np.ndarray:
        a = max(0, start_frame * FRAME - PRE_PAD)
        b = min(len(s.pcm) // 2, end_sample)
        return np.frombuffer(bytes(s.pcm[a * 2:b * 2]), dtype=np.int16).astype(np.float32) / 32768.0

    def _prompt(self, s: Session) -> str:
        text = " ".join(s.phrases)
        return text[-200:]

    def _phrase(self, s: Session, start: int, end: int) -> None:
        if s.cancelled:
            return
        audio = self._audio(s, start, end * FRAME + POST_PAD)
        t0 = time.monotonic()
        text, lang = self.engine.transcribe(audio, prompt=self._prompt(s), language=s.language)
        s.transcribe_s += time.monotonic() - t0
        if self.cfg.language in ("", "auto") and lang and not s.language:
            s.language = lang  # keep the language of the first phrase: detection on short phrases wobbles
        if not text or s.cancelled:
            return
        s.phrases.append(text)
        if s.mode == "live":
            out = text if s.style == "verbatim" else strip_fillers(text)
            if out:
                piece = joiner(s.typed, out) + out
                s.typed += piece
                if s.ptt:
                    s.held += piece  # the hotkey is still down: typing now would send Ctrl+Alt+<key>; type on release
                else:
                    s.jobs.append(self.inserter.submit(InsertJob(piece, self.cfg.insert, s.target)))
        live = self._live_text(s)
        self.ui(lambda: self.overlay.set_text(live))

    def _interim(self, s: Session, start: int, end_sample: int) -> None:
        try:
            if s.stopping or s.cancelled or s.seg.phrase_start != start:
                return
            text, _ = self.engine.transcribe(self._audio(s, start, end_sample), prompt=self._prompt(s), fast=True,
                                             language=s.language)
            if text and not s.stopping and s.seg.phrase_start == start:
                preview = self._live_text(s, extra=text)
                self.ui(lambda: self.overlay.set_text(preview))
        finally:
            s.interim_busy = False

    def _live_text(self, s: Session, extra: str = "") -> str:
        done = s.typed if s.mode == "live" else " ".join(s.phrases)
        return (done + joiner(done, extra) + extra + " …") if extra else done

    def _finalize(self, s: Session) -> None:
        if s.cancelled:
            return
        raw = ""
        for p in s.phrases:
            raw += joiner(raw, p) + p
        secs = len(s.pcm) / 2 / RATE
        if not raw.strip():
            why = "No speech heard." if not s.seg.heard else "Whisper heard no words."
            self.ui(lambda: self.overlay.set_state("idle", why, "", "Nothing was typed.", hide_after=3))
            log(f"[dictation] session {s.id}: nothing to type ({s.stop_reason})")
            self._idle(s)
            return
        note = ""
        polish_s = 0.0
        if s.mode == "live":
            final = s.typed
            if s.held:
                s.jobs.append(self.inserter.submit(InsertJob(s.held, self.cfg.insert, s.target)))
            for job in s.jobs:
                job.done.wait(20)
            missed = [j for j in s.jobs if j.outcome != "inserted"]
            outcome, detail = "inserted", f"{len(final)} characters as you spoke"
            if missed:
                # Everything that did not land goes on the clipboard together, in order.
                why = next((j.detail for j in missed if j.detail), "Typing timed out.")
                self.inserter.submit(InsertJob("".join(j.text for j in missed).strip(), "copy", 0)).done.wait(5)
                outcome, detail = "copied", why.replace("the text went", "the rest went")
        else:
            final = raw
            if s.style != "verbatim":
                self.ui(lambda: self.overlay.set_state("working", "Cleaning up", raw))
                res = cleanup.polish(raw, s.style, base_url=self.gateway, api_key=self.api_key,
                                     model=self.cfg.cleanup_model, prompt=self.cfg.cleanup_prompt)
                final, note, polish_s = res.text, res.note, res.seconds
            if s.cancelled:
                return
            job = self.inserter.submit(InsertJob(final, self.cfg.insert, s.target))
            job.done.wait(20)
            outcome, detail = job.outcome or "failed", job.detail or "timed out"
        self.history.append((raw, final))
        hint = detail if outcome != "inserted" else ""
        if note:
            hint = (hint + " " if hint else "") + f"Cleanup skipped: {note}; typed the transcript without filler sounds."
        title = {"inserted": "Typed", "copied": "Copied to the clipboard"}.get(outcome, "Could not type it")
        state = "done" if outcome == "inserted" else "error"
        self.ui(lambda: self.overlay.set_state(state, title, final, hint, hide_after=4 if state == "done" else 9))
        log(f"[dictation] session {s.id}: {secs:.1f} s audio, {len(s.phrases)} phrase(s), whisper {s.transcribe_s:.2f} s"
            f"{f', cleanup {polish_s:.2f} s' if polish_s else ''}{f' ({note})' if note else ''}; {outcome}: {detail}")
        self._idle(s)

    def _idle(self, s: Session) -> None:
        if self.session is s:
            self.session = None
            self.state = "idle"

    # ---------------------------------------------------------------- menu actions

    def set_option(self, key: str, value) -> None:
        setattr(self.cfg, key, value)
        if key == "button":
            self.overlay.set_button_visible(bool(value))
            if not value:
                self.overlay.show_bubble("Button hidden", "", f"{self.hotkey_text()} still works. Show it again from "
                                         "the tray: Voice typing row, Show button.", owner="idle")
                self.overlay._schedule_hide(5)
        try:
            save_setting(self.profile, key, value)
        except Exception as e:  # noqa: BLE001 - the change still applies until the app restarts
            log(f"[dictation] could not save dictation.{key}: {e}")

    def remember_position(self, x: int, y: int) -> None:
        write_state(self.profile, x=x, y=y)

    def paste_last(self) -> None:
        if not self.history:
            return
        threading.Thread(target=self._paste_again, daemon=True).start()

    def _paste_again(self) -> None:
        time.sleep(0.15)  # let the menu close
        target = self.last_external or self.ws.root_window(self.ws.foreground())  # the window you are in now
        job = self.inserter.submit(InsertJob(self.history[-1][1], self.cfg.insert, target))
        job.done.wait(10)

    def copy_last(self, raw: bool) -> None:
        if self.history:
            text = self.history[-1][0 if raw else 1]
            self.inserter.submit(InsertJob(text, "copy", 0))


def main(argv: list[str] | None = None) -> int:
    profile = prof.resolve_profile()
    try:
        app = App(profile)
    except OSError as e:
        if getattr(e, "winerror", None) == 10048 or getattr(e, "errno", None) in (98, 10048):
            log(f"[dictation] already running (port {profile['ports']['dictation']} is in use)")
            return 0
        raise
    return app.run()
