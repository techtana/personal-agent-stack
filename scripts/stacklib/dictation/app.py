"""The voice typing app: hotkey or button -> microphone -> VAD -> Whisper -> optional cleanup -> the focused window.
It also refines selected text: the refine button or its hotkey -> Ctrl+C -> the gateway's local model -> Ctrl+V over
the selection, with every suggestion kept in the refine log (refiner.py). What you dictate is kept in the voice
typing history (voicelog.py) for dictation.keep_minutes.

Threads: Tk main loop (buttons, bubble, history window); hotkeys (Win32 message loop); microphone (WinMM) which also
runs the VAD and the segmenter on each 32 ms frame; control (start, stop, cancel, in order); worker (Whisper and the
cleanup, one job at a time); inserter (clipboard and keystrokes, in order); a refine job's own thread while it waits
for the model; the local HTTP control endpoint.

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
from dataclasses import dataclass, field

import numpy as np

from .. import env_value
from .. import profile as prof
from . import (Config, cleanup, control, ensure_refine_section, hotkey, read_state, refine, save_setting, state_dir,
               transcriptions, write_state)
from . import api_key as transcription_key
from .audio import RATE, Recorder, RecorderError
from .engine import Engine
from .refinelog import LOG_NAME, RefineLog
from .refiner import Refiner
from .segment import FRAME, Event, Segmenter
from .textops import joiner, strip_fillers
from .voicelog import VOICE_LOG_NAME, VoiceLog
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


@dataclass
class CallJob:
    """Run fn(winsys, clipboard) on the inserter thread (the refine's Ctrl+C and Ctrl+V), in turn with the inserts."""
    fn: object
    done: threading.Event = field(default_factory=threading.Event)
    result: object = None
    error: BaseException | None = None
    abandoned: bool = False   # the caller gave up waiting: never press keys for it later


class Inserter(threading.Thread):
    """Puts text into the focused window, one job at a time, on the thread that owns the clipboard window."""

    def __init__(self, own_windows) -> None:
        super().__init__(name="dictation-insert", daemon=True)
        self.q: queue.Queue = queue.Queue()
        self.own_windows = own_windows   # callable -> set of our HWNDs

    def submit(self, job: InsertJob) -> InsertJob:
        self.q.put(job)
        return job

    def call(self, fn, timeout: float = 30.0):
        """fn(winsys, clipboard) on this thread; returns its result or raises its exception."""
        job = CallJob(fn)
        self.q.put(job)
        if not job.done.wait(timeout):
            job.abandoned = True
            raise TimeoutError("the clipboard thread did not answer")
        if job.error is not None:
            raise job.error
        return job.result

    def run(self) -> None:
        from . import winsys

        self.winsys = winsys
        self.clip = winsys.Clipboard()
        self.elevated = winsys.self_elevated()
        while True:
            job = self.q.get()
            if job is None:
                break
            if isinstance(job, CallJob):
                if job.abandoned:
                    continue
                try:
                    job.result = job.fn(winsys, self.clip)
                except BaseException as e:  # noqa: BLE001 - handed back to the caller
                    job.error = e
                job.done.set()
                continue
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
        self.voice_log = VoiceLog(state_dir(profile) / VOICE_LOG_NAME, keep_minutes=self.cfg.keep_minutes)
        self.counter = 0
        self.commands: queue.Queue = queue.Queue()
        self.jobs: queue.Queue = queue.Queue()
        self.hotkey_vk = 0
        self.hotkey_error = ""
        self.last_target = 0
        self.last_external = 0            # last foreground window that is not ours (see _track_focus)
        self.pid = os.getpid()
        self.rcfg = refine.Config.from_profile(profile, warn=lambda m: log(f"[refine] {m}"))
        self.refine_hotkey_error = ""
        self.menu_hotkey_error = ""       # the hotkey that opens the style menu at the caret
        self.refine_log = RefineLog(state_dir(profile) / LOG_NAME, keep_minutes=self.rcfg.keep_minutes)
        self._esc_refine = False
        self._esc_lock = threading.Lock()
        # Raises when another copy runs. Also serves Open WebUI's microphone (transcriptions.py) on the same Whisper,
        # for callers with DICTATION_BEARER, looked up on each request so a key added to .env later works at once.
        self.server = control.ControlServer(
            self.port, self.health, self.act, api_key=transcription_key, log=log,
            transcribe=lambda data, **kw: transcriptions.transcribe_with(self.engine, data, **kw))
        state = read_state(profile)
        pos = (int(state["x"]), int(state["y"])) if "x" in state and "y" in state else None
        winsys.set_dpi_aware()
        self.overlay = Overlay(self, self.cfg.button, pos, show_refine=self.rcfg.button,
                               saved_width=int(state.get("w") or 0))
        self.inserter = Inserter(self.overlay.windows)
        self.hotkeys = winsys.HotkeyThread(self._on_hotkey)
        self.refiner = Refiner(call=self.inserter.call, target=self._target, ui=RefineUI(self), cfg=self._refine_cfg,
                               refine_fn=self._refine_fn, log=self.refine_log, esc=self._refine_esc,
                               elevated=winsys.self_elevated(), ours=self._ours, busy_elsewhere=self._dictating,
                               logline=log)

    # ---------------------------------------------------------------- lifecycle

    def run(self) -> int:
        self.server.start()
        self.inserter.start()
        self.hotkeys.start()
        self._register_hotkey()
        threading.Thread(target=self._command_loop, name="dictation-control-loop", daemon=True).start()
        threading.Thread(target=self._worker_loop, name="dictation-worker", daemon=True).start()
        threading.Thread(target=self._track_focus, name="dictation-focus", daemon=True).start()
        threading.Thread(target=self._prune_logs, name="dictation-prune", daemon=True).start()
        self.engine.load_async()
        log(f"[dictation] ready: hotkey {self.hotkey_text()}, mode {self.cfg.mode}, cleanup {self.cfg.style} "
            f"({self.prompt_kind()} prompt), VAD {self.vad.name}, refine {self.refine_hotkey_text()} "
            f"({self.rcfg.default} via {self.rcfg.model}), style menu {self.menu_hotkey_text() or 'off'}, control http://127.0.0.1:{self.port}")
        problems = [p for p in (self.hotkey_error, self.refine_hotkey_error, self.menu_hotkey_error) if p]
        if problems:
            self.ui(lambda: self.overlay.set_state("error", "Hotkey not available", " ".join(problems),
                                                   "Pick another one in the tray's Settings tab; the buttons still work.",
                                                   hide_after=12))
        self.overlay.run()
        self.hotkeys.stop()
        self.server.stop()
        return 0

    def ui(self, fn) -> None:
        self.overlay.post(fn)

    def _ours(self, hwnd: int) -> bool:
        """A window of this app: the buttons, the bubble, a menu, the history window or a picker."""
        return hwnd in self.overlay.windows() or self.ws.window_pid(hwnd) == self.pid

    def _track_focus(self) -> None:
        """Remember the last window you used that is not ours, so a click on a button, a menu item or the history
        window's Revert still acts on the app you came from."""
        while True:
            hwnd = self.ws.root_window(self.ws.foreground())
            if hwnd and not self._ours(hwnd):
                self.last_external = hwnd
            time.sleep(0.25)

    def _target(self) -> int:
        hwnd = self.ws.root_window(self.ws.foreground())
        return self.last_external if not hwnd or self._ours(hwnd) else hwnd

    def _register_hotkey(self) -> None:
        dictate = None
        try:
            mods, vk = dictate = hotkey.parse(self.cfg.hotkey)
        except hotkey.HotkeyError as e:
            self.hotkey_error = f"{self.cfg.hotkey}: {e}"
        else:
            ok, err = self.hotkeys.register("dictate", mods, vk)
            if ok:
                self.hotkey_vk = vk
            else:
                self.hotkey_error = f"{self.hotkey_text()} is taken by another program ({err})."
                log(f"[dictation] {self.hotkey_error}")
        taken = {"the voice typing hotkey": dictate} if dictate else {}
        # refine.hotkey / refine.menu_hotkey: '' (or off) leaves the pencil button and its menu only.
        self.refine_hotkey_error = self._register_extra("refine", self.rcfg.hotkey, "Refine", taken)
        self.menu_hotkey_error = self._register_extra("refine_menu", self.rcfg.menu_hotkey, "Refine style menu", taken)

    def _register_extra(self, name: str, key: str, what: str, taken: dict) -> str:
        """Register one of the refine hotkeys; '' when it worked or is off, else what went wrong. A key registered
        here joins `taken`, so two settings naming the same key report it instead of failing silently."""
        if hotkey.is_off(key):
            return ""
        try:
            combo = hotkey.parse(key)
        except hotkey.HotkeyError as e:
            return f"{what} {key}: {e}"
        text = hotkey.label(key)
        for other, used in taken.items():
            if combo == used:
                return f"{what}: {text} is also {other}."
        ok, err = self.hotkeys.register(name, *combo)
        if not ok:
            problem = f"{what}: {text} is taken by another program ({err})."
            log(f"[refine] {problem}")
            return problem
        taken[f"the {what.lower()} hotkey"] = combo
        return ""

    def hotkey_text(self) -> str:
        return hotkey.label(self.cfg.hotkey)

    def refine_hotkey_text(self) -> str:
        """'Ctrl+Alt+R', or '' when refine.hotkey is empty or off."""
        key = (self.rcfg.hotkey or "").strip()
        return "" if hotkey.is_off(key) else hotkey.label(key)

    def menu_hotkey_text(self) -> str:
        """'Ctrl+Alt+Shift+R', or '' when refine.menu_hotkey is empty or off."""
        key = (self.rcfg.menu_hotkey or "").strip()
        return "" if hotkey.is_off(key) else hotkey.label(key)

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
                "idle_s": round(time.monotonic() - self.engine.last_used), "unload_after_min": self.cfg.unload_after_min,
                "hotkey": self.cfg.hotkey, "hotkey_ok": not self.hotkey_error, "mode": self.cfg.mode,
                "style": self.cfg.style, "language": self.cfg.language, "button": bool(self.cfg.button),
                "refine": {"hotkey": self.rcfg.hotkey, "hotkey_ok": not self.refine_hotkey_error,
                           "menu_hotkey": self.rcfg.menu_hotkey, "menu_hotkey_ok": not self.menu_hotkey_error,
                           "button": bool(self.rcfg.button), "default": self.rcfg.default, "model": self.rcfg.model,
                           "busy": self.refiner.busy, "log": str(self.refine_log.path),
                           "keep_minutes": self.rcfg.keep_minutes},
                "history": {"log": str(self.voice_log.path), "keep_minutes": self.cfg.keep_minutes},
                "transcriptions": bool(transcription_key()),  # Open WebUI's microphone needs DICTATION_BEARER
                "pid": os.getpid()}

    def act(self, name: str) -> dict:
        if name == "toggle":
            self.toggle("http")
        elif name == "start":
            self.commands.put(("start", "http"))
        elif name in ("stop", "cancel"):
            if name == "cancel" and self.refiner.cancel():
                return {"ok": True, "state": self.state}
            self.commands.put((name, "http"))
        elif name in ("show", "hide"):
            visible = name == "show"
            self.cfg.button = visible  # reported by /health at once; the Tk thread shows or hides and saves it
            self.ui(lambda: self.set_option("button", visible))
        elif name in ("show_refine", "hide_refine"):
            visible = name == "show_refine"
            self.rcfg.button = visible
            self.ui(lambda: self.set_refine_option("button", visible))
        elif name == "refine":
            return {"ok": self.refiner.start("", "http"), "state": self.state}
        elif name == "revert":
            return {"ok": self.refiner.revert("", "http"), "state": self.state}
        elif name == "quit":
            self.quit()
        elif name == "reload":
            self.reload()
        return {"ok": True, "state": self.state}

    def prompt_kind(self) -> str:
        return "custom" if self.cfg.cleanup_prompt else "built-in"

    def reload(self) -> None:
        """Take the settings that need no restart from the machine file: the cleanup prompt and how long the history
        keeps a dictation (the tray's Apply calls this after saving them). The next cleanup uses the prompt; a
        shorter keep_minutes deletes older entries at once."""
        fresh = Config.from_profile(prof.resolve_profile(self.profile.get("name") or None))
        self.cfg.cleanup_prompt = fresh.cleanup_prompt
        self._set_voice_keep(fresh.keep_minutes)
        log(f"[dictation] settings reloaded: {self.prompt_kind()} cleanup prompt, history kept {self.voice_keep_text()}")

    def _set_voice_keep(self, minutes: float) -> int:
        """Use a new dictation.keep_minutes; returns how many history entries it deleted."""
        self.cfg.keep_minutes = self.voice_log.keep_minutes = minutes
        return self.voice_log.prune()

    def quit(self) -> None:
        log("[dictation] quitting")
        self.ui(self.overlay.quit)

    # ---------------------------------------------------------------- triggers

    def toggle(self, source: str) -> None:
        if self.state == "idle" and self.refiner.busy:
            self.ui(lambda: self.overlay.show_bubble("Still refining the selection", "", "Esc cancels it.",
                                                     ink="#8cc8ff", owner="working", source="refine"))
        elif self.state == "idle":
            self.commands.put(("start", source))
        elif self.state == "listening":
            self.commands.put(("stop", source))
        else:
            self.ui(lambda: self.overlay.show_bubble("Still finishing the last one", "", "One moment.",
                                                     ink="#8cc8ff", owner="working"))

    def _dictating(self) -> str:
        return "Finish dictating first" if self.state != "idle" else ""

    def _on_hotkey(self, name: str) -> None:
        if name == "cancel":
            self.commands.put(("cancel", "esc"))
            return
        if name == "refine_cancel":
            # Off this thread: cancelling unregisters Esc, which waits for this (the hotkey) thread to answer.
            threading.Thread(target=self.refiner.cancel, name="dictation-refine-cancel", daemon=True).start()
            return
        if name == "refine":
            self.refiner.start("", "hotkey")
            return
        if name == "refine_menu":
            self._style_menu_at_caret()
            return
        if self.refiner.busy:
            self.toggle("hotkey")  # says it is still refining
            return
        if self.state == "idle":
            self.commands.put(("start", "hotkey"))
            threading.Thread(target=self._watch_hold, name="dictation-ptt", daemon=True).start()
        else:
            self.toggle("hotkey")

    def _style_menu_at_caret(self) -> None:
        """The style menu hotkey (on the hotkey thread, so only quick calls here): remember the window you are in,
        find its text caret (or the mouse pointer when it shows none) and let the Tk thread open the menu there."""
        why = self._dictating() or ("Still working on the last selection" if self.refiner.busy else "")
        if why:
            hint = "Esc cancels it." if self.refiner.busy else "Try again when it is done."
            self.refiner.ui.note(why, "", hint)
            return
        target = self._target()
        point = self.ws.caret_pos(self.ws.foreground()) or self.ws.cursor_pos()
        self.ui(lambda: self.overlay.style_menu_at(point, target))

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
        if self.refiner.busy:
            return
        target = self._target()
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
        self._remember(s, raw, final, outcome, secs, note)
        hint = detail if outcome != "inserted" else ""
        if note:
            hint = (hint + " " if hint else "") + f"Cleanup skipped: {note}; typed the transcript without filler sounds."
        title = {"inserted": "Typed", "copied": "Copied to the clipboard"}.get(outcome, "Could not type it")
        state = "done" if outcome == "inserted" else "error"
        self.ui(lambda: self.overlay.set_state(state, title, final, hint, hide_after=4 if state == "done" else 9))
        log(f"[dictation] session {s.id}: {secs:.1f} s audio, {len(s.phrases)} phrase(s), whisper {s.transcribe_s:.2f} s"
            f"{f', cleanup {polish_s:.2f} s' if polish_s else ''}{f' ({note})' if note else ''}; {outcome}: {detail}")
        self._idle(s)

    def _remember(self, s: Session, raw: str, final: str, outcome: str, secs: float, note: str) -> None:
        """Keep the dictation in the voice typing history for dictation.keep_minutes (History, Paste last again)."""
        if not (raw or final).strip():
            return
        try:
            hwnd = self.ws.root_window(s.target) if s.target else 0
            app = self.ws.process_name(self.ws.window_pid(hwnd)) if hwnd else ""
            window = self.ws.window_title(hwnd)[:200] if hwnd else ""
        except Exception:  # noqa: BLE001 - the window may be gone; the text still counts
            app = window = ""
        try:
            self.voice_log.append({"kind": "dictation", "mode": s.mode, "style": s.style, "app": app, "window": window,
                                   "before": raw, "after": final, "status": outcome, "note": note,
                                   "seconds": round(secs, 1)})
        except OSError as e:
            log(f"[dictation] could not write the history: {type(e).__name__}")

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
                self.overlay.show_bubble("Mic button hidden", "", f"{self.hotkey_text()} still works. Show it again "
                                         "from the tray: Voice typing row, Show mic.", owner="idle")
                self.overlay._schedule_hide(5)
        try:
            save_setting(self.profile, key, value)
        except Exception as e:  # noqa: BLE001 - the change still applies until the app restarts
            log(f"[dictation] could not save dictation.{key}: {e}")

    def remember_position(self, x: int, y: int, width: int = 0) -> None:
        write_state(self.profile, x=x, y=y, w=width)

    # ---------------------------------------------------------------- refine selected text

    def _refine_cfg(self, quiet: bool = False) -> refine.Config:
        """The refine settings as the machine file has them now, so styles you add and a new keep_minutes apply
        without a restart. The hotkey stays the one registered at start."""
        try:
            fresh = refine.Config.from_profile(prof.resolve_profile(self.profile.get("name")))
        except Exception as e:  # noqa: BLE001 - a typo in the YAML must not break the button
            if not quiet:
                log(f"[refine] could not read the machine profile ({e}); using the settings from start-up")
            return self.rcfg
        fresh.hotkey = self.rcfg.hotkey
        self.rcfg = fresh
        self.refine_log.keep_minutes = fresh.keep_minutes
        return fresh

    def _prune_logs(self) -> None:
        """Delete refine log entries older than refine.keep_minutes and voice typing history entries older than
        dictation.keep_minutes: at start, then once a minute, so your text leaves the disk within a minute of
        expiring, whether or not you refine or dictate again."""
        while True:
            self.prune_once()
            time.sleep(60)

    def prune_once(self) -> None:
        for tag, step in (("refine", self._prune_refine), ("dictation", self._prune_voice)):
            try:
                removed = step()
                if removed:
                    log(f"[{tag}] deleted {removed} expired history entr{'y' if removed == 1 else 'ies'}")
            except Exception as e:  # noqa: BLE001 - keep trying; the next minute may work
                log(f"[{tag}] could not prune the history: {type(e).__name__}")

    def _prune_refine(self) -> int:
        self._refine_cfg(quiet=True)   # the tray may have changed refine.keep_minutes
        return self.refine_log.prune()

    def _prune_voice(self) -> int:
        minutes = self.cfg.keep_minutes
        try:   # the tray may have changed dictation.keep_minutes; a YAML typo keeps the last value
            minutes = Config.from_profile(prof.resolve_profile(self.profile.get("name") or None)).keep_minutes
        except Exception:  # noqa: BLE001
            pass
        return self._set_voice_keep(minutes)

    def voice_keep_text(self) -> str:
        """'30 minutes': how long the voice typing history keeps a dictation."""
        return refine.keep_text(self.cfg.keep_minutes)

    def refine_keep_text(self) -> str:
        """'30 minutes': how long the refine log keeps an entry, for the History window and the bubbles."""
        return refine.keep_text(self.rcfg.keep_minutes)

    def _refine_fn(self, text: str, style, *, model: str, timeout: float):
        return refine.refine_text(text, style, base_url=self.gateway, api_key=self.api_key, model=model,
                                  timeout=timeout)

    def _refine_esc(self, on: bool) -> None:
        """Esc cancels a refine while the model works; it is only taken from other apps for that long. Never call
        this on the hotkey thread: the hotkey thread does the (un)registering and this waits for its answer."""
        with self._esc_lock:
            if on == self._esc_refine:
                return
            self._esc_refine = on
            if on:
                self.hotkeys.register("refine_cancel", 0, hotkey.VK_ESCAPE)
            else:
                self.hotkeys.unregister("refine_cancel")

    def refine_choices(self) -> tuple[list, str]:
        cfg = self._refine_cfg()
        return refine.styles(cfg, warn=lambda m: log(f"[refine] {m}")), cfg.default

    def refine_summary(self) -> str:
        cfg = self._refine_cfg()  # the tray's Settings tab may have changed the default since start-up
        return f"A click rewrites the selection as {refine.style_named(cfg, None).name} with {cfg.model} on this PC."

    def refine_busy(self) -> bool:
        return self.refiner.busy

    def refine_click(self) -> None:
        self.refiner.start("", "button")

    def refine_with(self, style: str, target: int = 0) -> None:
        self.refiner.start(style, "style-menu" if target else "menu", target)

    def refine_revert(self, entry: str = "", target: int = 0) -> None:
        self.refiner.revert(entry, "history" if entry else "style-menu" if target else "menu", target)

    def set_refine_option(self, key: str, value) -> None:
        setattr(self.rcfg, key, value)
        if key == "button":
            self.overlay.set_refine_visible(bool(value))
            if not value:
                key_note = f"{self.refine_hotkey_text()} still refines the selection. " if self.refine_hotkey_text() else ""
                self.overlay.show_bubble("Refine button hidden", "", key_note + "Show it again from the tray (Show pencil) or the mic button's "
                                         "menu.", owner="idle")
                self.overlay._schedule_hide(5)
        elif key == "default":
            name = refine.style_named(self.rcfg, value).name
            users = f"A click and {self.refine_hotkey_text()} now use it." if self.refine_hotkey_text() else                 "A click on the pencil now uses it."
            self.overlay.show_bubble("Refine style chosen", name, users, owner="idle", source="refine")
            self.overlay._schedule_hide(3, "refine")
        try:
            save_setting(self.profile, key, value, section="refine")
        except Exception as e:  # noqa: BLE001 - the change still applies until the app restarts
            log(f"[refine] could not save refine.{key}: {e}")

    def edit_refine_styles(self) -> None:
        """Open the machine file, with a commented example `refine:` section added if it has none."""
        path = prof.machine_file(self.profile.get("name"))
        try:
            added = ensure_refine_section(path)
            if os.name == "nt":
                try:
                    os.startfile(path)  # type: ignore[attr-defined]
                except OSError:
                    import subprocess

                    subprocess.Popen(["notepad.exe", str(path)])
        except Exception as e:  # noqa: BLE001
            self.overlay.show_bubble("Could not open the styles", str(e), owner="idle", source="refine")
            self.overlay._schedule_hide(8, "refine")
            return
        self.overlay.show_bubble(f"Opened {path.name}", "Your styles go under refine: prompts:" +
                                 (" (an example was added at the end)." if added else "."),
                                 "Save the file; the refine menu shows them the next time you open it.",
                                 owner="idle", source="refine")
        self.overlay._schedule_hide(10, "refine")

    def copy_text(self, text: str) -> None:
        self.inserter.submit(InsertJob(text, "copy", 0))


    def last_dictation(self) -> dict | None:
        """The newest dictation the history still keeps (dictation.keep_minutes)."""
        return self.voice_log.last()

    def paste_last(self) -> None:
        last = self.last_dictation()
        if last:
            self.paste_text(str(last["after"]))

    def paste_text(self, text: str) -> None:
        """Type `text` again into the app you came from (a menu item or the History window's button)."""
        if text:
            threading.Thread(target=self._paste_again, args=(text,), daemon=True).start()

    def _paste_again(self, text: str) -> None:
        time.sleep(0.15)  # let the menu close
        target = self.last_external or self.ws.root_window(self.ws.foreground())  # the window you are in now
        job = self.inserter.submit(InsertJob(text, self.cfg.insert, target))
        job.done.wait(10)

    def copy_last(self, raw: bool) -> None:
        last = self.last_dictation()
        text = str((last or {}).get("before" if raw else "after") or "")
        if text:
            self.inserter.submit(InsertJob(text, "copy", 0))


class RefineUI:
    """The refine button's states and bubble, for Refiner (which runs on its own thread)."""

    def __init__(self, app: App) -> None:
        self.app = app

    def _set(self, state: str, title: str, body: str, hint: str, hide_after: float = 0.0) -> None:
        self.app.ui(lambda: self.app.overlay.set_state(state, title, body, hint, hide_after=hide_after, which="refine"))

    def working(self, title: str, body: str = "", hint: str = "") -> None:
        self._set("working", title, body, hint)

    def done(self, title: str, body: str = "", hint: str = "") -> None:
        self._set("done", title, body, hint, hide_after=6)

    def error(self, title: str, body: str = "", hint: str = "") -> None:
        self._set("error", title, body, hint, hide_after=10)

    def cancelled(self, title: str, body: str = "", hint: str = "") -> None:
        self._set("idle", title, body, hint, hide_after=2.5)

    def note(self, title: str, body: str = "", hint: str = "") -> None:
        """A message that leaves the button's state alone (it may be spinning)."""
        self.app.ui(lambda: self.app.overlay.show_bubble(title, body, hint, ink="#8cc8ff", owner="note",
                                                         source="refine"))


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
