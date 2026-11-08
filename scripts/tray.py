#!/usr/bin/env python3
"""Agent Stack tray app: keeps the stack's services running in the background and shows their status.

It lives in the notification area (on Windows it starts among the hidden icons). Left-click or "Show status" opens a
window with three tabs:
  Overview  each service's health with start/stop and links into the UIs ("Not installed" when its feature is not),
            the models loaded in Ollama, the features the installer offers (installed, on or off, linked to the
            stack; what each takes on this PC; Add features opens the installer; OpenClaw's Use gateway button), and
            where the Hugging Face cache is
  Usage     every model the stack ran (gateway, Whisper, ComfyUI, direct Ollama calls): requests, tokens, audio,
            images, speed and cost per model, service or client, with a per-day chart
  Settings  models, context sizes, tracing and Ollama runtime options; Apply writes machines/<HOST>.yaml,
            rebuilds the generated configs and restarts what the change affects
The icon colour summarises health: green all up, amber some down, red gateway down.

Run it detached with `uv run scripts/stack.py tray`, or inline with `uv run scripts/stack.py tray --foreground`.
Started this way it is not tied to a terminal or Claude Code session, so the services it starts keep running.
"""
from __future__ import annotations

import os
import queue
import re
import sys
import threading
import time
import tkinter as tk
import traceback
import webbrowser
from datetime import date, datetime, timezone
from pathlib import Path
from tkinter import messagebox, ttk

LOG_FILE = Path(__file__).resolve().parents[1] / ".run" / "logs" / "tray.log"
# `stack.py tray` watches the log for these lines (stacklib/startup.py), so keep the two in step.
READY = "[tray] ready"
FAILED = "[tray] start-up failed:"


def startup_failure_text(exc: BaseException) -> str:
    """Why the tray could not start and what to do about it, for the message box shown under pythonw."""
    repo = LOG_FILE.parents[2]
    text = " ".join(str(exc).split()) or type(exc).__name__
    missing = re.search(r"no machine profile at (.+?);", text)
    if missing:
        reason = f"This computer has no machine profile: {missing.group(1)} does not exist."
        todo = f"Open a terminal in {repo} and run\n    uv run scripts/stack.py doctor --write-profile\nthen start the tray again."
    elif isinstance(exc, ImportError):
        reason = f"A Python package the tray needs could not be loaded: {text}"
        todo = (f"Open a terminal in {repo} and run\n    uv sync\nthen start the tray again. If the message mentions an "
                "Application Control policy, Windows Smart App Control blocked the file.")
    else:
        reason = f"{type(exc).__name__}: {text}"
        todo = f"Start it again from a terminal in {repo} with\n    uv run scripts/stack.py tray"
    return f"{reason}\n\n{todo}\n\nDetails are in {LOG_FILE}"


def _report_startup_failure(exc_type, exc, tb) -> None:
    """An uncaught error under pythonw: nobody sees the traceback, so log it and say on screen why the tray stopped."""
    traceback.print_exception(exc_type, exc, tb)
    print(f"{FAILED} {type(exc).__name__}: {' '.join(str(exc).split())}")
    if issubclass(exc_type, KeyboardInterrupt):
        return
    pidfile = LOG_FILE.parents[1] / "pids" / "tray.pid"
    try:  # give up the single-instance claim now, so a retry works while the message is still open
        if pidfile.read_text(encoding="utf-8").split()[0] == str(os.getpid()):
            pidfile.unlink()
    except (OSError, IndexError):
        pass
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Agent Stack could not start", startup_failure_text(exc), parent=root)
        root.destroy()
    except tk.TclError:  # no display to show it on; the log has it
        pass


if __name__ == "__main__" and (sys.stdout is None or not sys.stdout.isatty()):
    # pythonw has no console: keep a log instead, opened before the imports below so an import error lands in it too.
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    sys.stdout = sys.stderr = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
    sys.excepthook = _report_startup_failure

sys.path.insert(0, str(Path(__file__).resolve().parent))
import psutil  # noqa: E402
import pystray  # noqa: E402
from PIL import ImageTk  # noqa: E402

from stacklib import IS_WINDOWS, clients, media, ollama, process_metrics, procname, profile as prof, services  # noqa: E402
from stacklib.icon import COLORS, make_icon  # noqa: E402
from stacklib import settings as cfg  # noqa: E402
from stacklib import comfy_usage, features, startup, usage, usage_log  # noqa: E402

POLL_SECONDS = 10
CLIENT_SECONDS = 60  # between feature and Hugging Face checks: measuring the cache walks every file in it
START_TIMEOUT = 180  # seconds a started service gets to answer its health check
RESOURCE_SECONDS = 5  # pause between process samples while the Resources tab is on screen
RESOURCES_TAB = 3
LABELS = {
    "ollama": "Ollama",
    "phoenix": "Phoenix",
    "litellm": "LiteLLM gateway",
    "orchestrator": "Orchestrator MCP",
    "open_webui": "Open WebUI",
    "comfyui": "ComfyUI",
    "kokoro": "Kokoro",
    "dictation": "Voice typing",
}
ROLES = {
    "ollama": "runs the local models",
    "phoenix": "trace viewer",
    "litellm": "one API for every model",
    "orchestrator": "department delegation for agents",
    "open_webui": "chat in the browser",
    "comfyui": "image, video and music generation",
    "kokoro": "text to speech",
    "dictation": "speak into any app (Whisper)",
}
CLIENTS = (("huggingface", "Hugging Face cache", "model weights for Python tools"),)
FONT = "Segoe UI" if IS_WINDOWS else "TkDefaultFont"

# Window palette (light / dark): neutral surfaces, one blue accent for data, status colours only for state.
# Every colour used for text (ink2, muted, accent, good, warn, bad) is at least 4.5:1 on page and card, and accent_ink
# at least 4.5:1 on accent (WCAG AA); check changes with .claude/skills/ux-rules/scripts/contrast.py.
THEMES = {
    "light": {
        "page": "#f3f3f1", "card": "#fcfcfb", "ink": "#0b0b0b", "ink2": "#52514e", "muted": "#6b6a65",
        "grid": "#e1e0d9", "border": "#dcdbd4", "accent": "#2368c0", "accent_ink": "#ffffff", "hover": "#ebeae5",
        "good": "#087a08", "warn": "#8a5f00", "bad": "#c03535", "select": "#dbe8f8",
    },
    "dark": {
        "page": "#111110", "card": "#1a1a19", "ink": "#f0efec", "ink2": "#c3c2b7", "muted": "#898781",
        "grid": "#2c2c2a", "border": "#33332f", "accent": "#3987e5", "accent_ink": "#0b0b0b", "hover": "#252523",
        "good": "#0ca30c", "warn": "#fab219", "bad": "#e05252", "select": "#1f3a5c",
    },
}
RANGES = [("Today", 1), ("7 days", 7), ("30 days", 30)]
SEP = "\x1f"  # joins a model and a client in a Usage table row id


def ui_links(p: dict) -> dict[str, str]:
    ports = p["ports"]
    return {
        "open_webui": f"http://127.0.0.1:{ports['open_webui']}",
        "phoenix": f"http://127.0.0.1:{ports['phoenix']}",
        "litellm": f"http://127.0.0.1:{ports['litellm']}/ui",
        "comfyui": f"http://127.0.0.1:{ports['comfyui']}",
    }


def system_theme() -> str:
    if IS_WINDOWS:
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
                return "light" if winreg.QueryValueEx(k, "AppsUseLightTheme")[0] else "dark"
        except OSError:
            pass
    return "light"


def compact(n: float) -> str:
    n = float(n)
    for div, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "k")):
        if abs(n) >= div:
            v = n / div
            return f"{v:.1f}{suffix}" if v < 100 else f"{v:.0f}{suffix}"
    return f"{n:.0f}"


def human_bytes(n: int) -> str:
    return f"{n / 2**30:.1f} GB" if n >= 2**30 else f"{n / 2**20:.0f} MB"


def waited(seconds: float | None) -> str:
    """'... 12 s'; just '...' in the first second or when the time is unknown."""
    return f"... {int(seconds)} s" if seconds and seconds >= 1 else "..."


class TextVar:
    """The get/set of a tk variable for a Text widget (which has none), so the Settings tab treats a text box like
    every other control."""

    def __init__(self, widget: tk.Text) -> None:
        self.widget = widget

    def get(self) -> str:
        return self.widget.get("1.0", "end-1c")

    def set(self, value: str) -> None:
        self.widget.delete("1.0", "end")
        self.widget.insert("1.0", value)
        self.widget.edit_reset()           # Ctrl+Z must not take the box back past what was loaded
        self.widget.edit_modified(False)   # a load is not an edit (see TrayApp._text_edited)

    def replace(self, value: str) -> None:
        """Set the text as one edit, which Ctrl+Z takes back whole (Restore default)."""
        w = self.widget
        w.configure(autoseparators=False)
        w.edit_separator()
        w.delete("1.0", "end")
        w.insert("1.0", value)
        w.edit_separator()
        w.configure(autoseparators=True)


class TrayApp:
    def __init__(self, autostart: bool = True) -> None:
        self.profile = prof.resolve_profile()
        usage_log.configure(self.profile)  # the warm-up and the ComfyUI collector record into traces/usage
        usage_log.sync_switch(self.profile)  # and services started earlier follow "Write usage traces"
        self.managed = [s for s in services.SERVICE_ORDER if s in services.commands(self.profile)]
        self.rows: dict[str, dict] = {}  # service -> newest status row
        self.row_checked: dict[str, float] = {}  # service -> when the check behind its row began (monotonic)
        self.rows_lock = threading.Lock()
        self.loaded: list[dict] = []
        self.client_status: dict[str, clients.ClientStatus] = {}
        self.clients_checked = 0.0  # monotonic; 0 = never
        self.hardware = features.hardware(self.profile)
        self.feature_status: dict[str, features.Status] = {}  # empty until the first check: service rows as before
        self.feature_est = features.estimates(self.profile, self.hardware)
        self.installer: tuple[int, str | None] | None = None  # (pid, start time) of the installer window we opened
        self.installer_note = ""  # what the last Add features click did, shown under the Features card
        self.openclaw_busy = False
        self.openclaw_result = ""  # why the last Use gateway click failed, shown until the next click
        self.dictation_button: bool | None = None  # floating mic button visible? None while voice typing is down
        self.refine_button: bool | None = None     # the refine (pencil) button next to it, the same way
        self.usage_data: dict | None = None
        self.usage_notes: list[str] = []  # model use the Usage tab cannot count, while it can happen
        self.usage_notes_at = -1e9  # monotonic time of the last check
        self.usage_days = 7
        self.usage_group = "served"
        self.process_sampler = process_metrics.ProcessSampler()
        self.process_rows: list[dict] = []
        self.sampling = False
        self.sample_job: str | None = None
        self.sample_failures = 0
        # service -> ("start" | "stop", monotonic start time) while that action runs; the tuple's identity tells a
        # worker whether a newer click (Stop during a start) has taken over its row. Changed on the Tk thread only.
        self.pending: dict[str, tuple[str, float]] = {}
        self.service_locks = {s: threading.Lock() for s in services.SERVICE_ORDER}
        self.tick_job: str | None = None
        self.created: dict[int, float] = {}  # pid -> process creation time, for "Starting... N s"
        self.problems: dict[str, tuple[str, str, Path]] = {}  # service -> (action, reason shown on its row, log file)
        self.busy = ""  # set while settings are applied; every service control waits for it
        self.checked_at = ""
        self.ui_queue: queue.Queue = queue.Queue()
        self.stop_event = threading.Event()
        procname.set_app_id("tray")  # the taskbar shows the window icon below, not Python's
        self.root = tk.Tk()
        self.root.withdraw()
        # The tray's icon on every window (title bar, taskbar, Alt+Tab), kept referenced for Tk.
        self.window_icons = [ImageTk.PhotoImage(make_icon(COLORS["ok"], n)) for n in (16, 32, 64)]
        self.root.iconphoto(True, *self.window_icons)
        self.window: tk.Toplevel | None = None
        self.refresh_lock = threading.Lock()
        self.icon_color = COLORS["idle"]
        self.icon = pystray.Icon("agent-stack", make_icon(COLORS["idle"]), "Agent Stack: starting", menu=self._menu())
        if autostart:
            self._act("start", self.managed)
            # Load the primary model now, so the first chat after login does not wait for it. Ollama may still be
            # starting at login, hence the wait.
            threading.Thread(target=lambda: print(f"[tray] {ollama.warm_primary(self.profile, wait=300)}"), daemon=True).start()

    # ---------- state ----------
    def refresh(self) -> None:
        checked = time.monotonic()
        rows = services.status(self.profile)
        self.loaded = ollama.ps(f"http://127.0.0.1:{self.profile['ports']['ollama']}")
        self._store_rows(rows, checked)
        self._check_dictation()
        self._collect_usage()
        if checked - self.clients_checked >= CLIENT_SECONDS or not self.clients_checked:
            self.clients_checked = checked
            self.client_status = self._check_clients()
            self._check_features()
        self.checked_at = datetime.now().strftime("%H:%M:%S")
        # Refreshes come from the poller and from start/stop threads; pystray's Windows backend frees the old icon
        # handle on every swap, so two concurrent swaps fail with WinError 1402. Serialise, and swap only on change.
        with self.refresh_lock:
            up = {s for s, r in self.rows.items() if r["healthy"]}
            wanted = ["ollama", *self.managed]
            n_up = sum(1 for s in wanted if s in up)
            if "litellm" not in up or "ollama" not in up:
                color = COLORS["bad"]
            elif n_up == len(wanted):
                color = COLORS["ok"]
            else:
                color = COLORS["warn"]
            if color != self.icon_color:
                self.icon.icon = make_icon(color)
                self.icon_color = color
            activity = self._activity()
            self.icon.title = f"Agent Stack: {n_up}/{len(wanted)} up" + (f" ({activity})" if activity else "")
            self.icon.update_menu()
        self.ui_queue.put(self._render_window)
        self.refresh_usage()

    def _check_dictation(self) -> None:
        """Whether voice typing's floating button is showing, from its own control endpoint."""
        if not self.rows.get("dictation", {}).get("healthy"):
            self.dictation_button = self.refine_button = None
            return
        from stacklib.dictation import control

        try:
            health = control.call(int(self.profile["ports"]["dictation"]), "health", 1.5)
            self.dictation_button = bool(health.get("button", True))
            refine = health.get("refine")
            self.refine_button = bool(refine.get("button", True)) if isinstance(refine, dict) else None
        except (OSError, ValueError, AttributeError):
            self.dictation_button = self.refine_button = None

    def _collect_usage(self) -> None:
        """ComfyUI's finished jobs into usage records: Open WebUI asks ComfyUI for images directly, past the gateway."""
        if not self.rows.get("comfyui", {}).get("healthy"):
            return
        try:
            n = comfy_usage.collect(f"http://127.0.0.1:{self.profile['ports']['comfyui']}")
        except Exception as e:  # noqa: BLE001 - the status poll must go on whatever ComfyUI's history holds
            print(f"[tray] ComfyUI usage collection failed: {e}")
            return
        if n:
            print(f"[tray] recorded {n} ComfyUI job(s) for the Usage tab")

    def _check_clients(self) -> dict[str, clients.ClientStatus]:
        out = {}
        for key, fn in (("huggingface", clients.huggingface),
                        ("openclaw", lambda: clients.openclaw(self.profile["ports"]["litellm"]))):
            try:
                out[key] = fn()
            except Exception as e:  # noqa: BLE001 - a bad config file must not stop the poller
                out[key] = clients.ClientStatus("warn", "Not checked", str(e) or type(e).__name__)
        return out

    def _check_features(self) -> None:
        """What is installed, on and linked (stacklib/features.py), and what each feature takes with the models that
        are loaded now. Reuses the OpenClaw check _check_clients just made."""
        try:
            self.feature_status = features.statuses(self.profile, openclaw=self.client_status.get("openclaw"))
            self.feature_est = features.estimates(self.profile, self.hardware, self.loaded)
        except Exception as e:  # noqa: BLE001 - the poller must go on; the card keeps its last reading
            print(f"[tray] feature check failed: {e}")

    def _store_rows(self, rows: list[dict], checked: float) -> None:
        """Keep each service's newest reading, so a slow poll that began before an action finished cannot undo it."""
        with self.rows_lock:
            new = dict(self.rows)
            for r in rows:
                if checked >= self.row_checked.get(r["service"], 0.0):
                    new[r["service"]] = r
                    self.row_checked[r["service"]] = checked
            self.rows = new  # replaced, never changed in place: other threads read it without the lock

    def _activity(self) -> str:
        if self.busy:
            return self.busy
        pending = dict(self.pending)
        if not pending:
            return ""
        verbs = {a for a, _ in pending.values()}
        verb = "starting" if verbs == {"start"} else "stopping" if verbs == {"stop"} else "changing"
        return f"{verb} {next(iter(pending)) if len(pending) == 1 else f'{len(pending)} services'}"

    def refresh_usage(self) -> None:
        try:
            self.usage_data = usage.summarize(self.usage_days, self.usage_group)
            if time.monotonic() - self.usage_notes_at > 60:  # reads Open WebUI's settings: once a minute is plenty
                self.usage_notes, self.usage_notes_at = usage.uncounted(self.profile), time.monotonic()
        except Exception as e:  # noqa: BLE001 - a malformed trace file must not break the window
            print(f"[tray] usage summary failed: {e}")
            return
        self.ui_queue.put(self._render_usage)

    def _poll(self) -> None:
        while not self.stop_event.is_set():
            try:
                self.refresh()
            except Exception as e:  # noqa: BLE001 - the poller must survive transient errors
                print(f"[tray] refresh failed: {e}")
            self.stop_event.wait(POLL_SECONDS)

    def _act(self, action: str, svcs: list[str]) -> None:
        """Start or stop services. Runs on the Tk thread: the rows change at once, each service's work runs in its own
        thread, and a start waits only for the service it started."""
        now = time.monotonic()
        for svc in svcs:
            if self.pending.get(svc, ("",))[0] == action:
                continue
            entry = (action, now)
            self.pending[svc] = entry
            self.problems.pop(svc, None)
            threading.Thread(target=self._run_action, args=(svc, entry), daemon=True).start()
        self._render_services()
        self._tick_soon()
        if self._window_built():
            self._settings_dirty()

    def _run_action(self, svc: str, entry: tuple[str, float]) -> None:
        action = entry[0]
        log = services.log_file(self.profile, svc)
        problem = None  # (what to show on the row, log to open)
        try:
            offset = log.stat().st_size if log.exists() else 0
            # A Stop clicked during a start waits here until the start has launched the process, then stops it.
            with self.service_locks[svc]:
                if self.pending.get(svc) is not entry:
                    return
                reasons = (services.start if action == "start" else services.stop)(self.profile, [svc])
            if svc in reasons:
                problem = (f"Not {'started' if action == 'start' else 'stopped'}: {reasons[svc]}.", log)
            deadline = time.monotonic() + START_TIMEOUT
            while action == "start" and not problem and self.pending.get(svc) is entry:
                row = services.probe(self.profile, svc)
                if row["healthy"]:
                    break
                if row["state"] == "stopped":
                    last = services.last_log_line(self.profile, svc, since=offset)
                    problem = (f"Stopped while starting. Last log line: {last}" if last else "Stopped while starting, without writing to its log.", log)
                elif time.monotonic() > deadline:
                    problem = (f"No answer from its health check after {START_TIMEOUT // 60} minutes; it may still be loading.", log)
                else:
                    time.sleep(1)
                    continue
                break
        except Exception as e:  # noqa: BLE001 - the row says what failed; the traceback goes to tray.log
            traceback.print_exc()
            problem = (f"Could not {action}: {e}", LOG_FILE)
        checked = time.monotonic()
        row = services.probe(self.profile, svc)
        if problem:
            print(f"[tray] {svc}: {problem[0]}")
        self.ui_queue.put(lambda: self._action_done(svc, entry, row, checked, problem))

    def _action_done(self, svc: str, entry: tuple[str, float], row: dict, checked: float, problem) -> None:
        if self.pending.get(svc) is not entry:
            return  # a newer click took over this row
        del self.pending[svc]
        if problem:
            self.problems[svc] = (entry[0], *problem)
        self._store_rows([row], checked)
        self._render_services()
        if not self.pending and self._window_built():
            self._settings_dirty()  # Apply and Revert wait for service changes to finish
        self.refresh_soon()

    def _tick_soon(self) -> None:
        if self.tick_job is None:
            self.tick_job = self.root.after(1000, self._tick)

    def _tick(self) -> None:
        """Advance the seconds shown on starting and stopping rows, once a second while there are any."""
        self.tick_job = None
        self._render_services()
        if self.pending or any(r["state"] == "starting" for r in self.rows.values()):
            self._tick_soon()

    def _on_ui(self, fn) -> None:
        """Run fn on the Tk thread: at once for a window click, through the UI queue for the tray menu's thread."""
        if threading.current_thread() is threading.main_thread():
            fn()
        else:
            self.ui_queue.put(fn)

    def refresh_soon(self) -> None:
        threading.Thread(target=self.refresh, daemon=True).start()

    # ---------- actions ----------
    def _running(self, svc: str) -> bool:
        """Running, starting, or being started: what Stop applies to."""
        pending = self.pending.get(svc)
        return pending[0] == "start" if pending else self.rows.get(svc, {}).get("state", "stopped") != "stopped"

    def start_all(self, *_):
        self._on_ui(lambda: self._act("start", [s for s in self.managed if not self._running(s) and s not in self.pending]))

    def stop_all(self, *_):
        self._on_ui(lambda: self._act("stop", [s for s in self.managed if self._running(s)]))

    def toggle(self, svc: str) -> None:
        self._act("stop" if self._running(svc) else "start", [svc])

    def set_gpu_mode(self, mode: str) -> None:
        """Hand the GPU to chat or to media (plan G1). Runs off the Tk thread: unloading a model takes seconds."""
        def run() -> None:
            try:
                msg = media.gpu_mode(self.profile, mode)
            except Exception as e:  # noqa: BLE001 - shown on the window, never fatal
                msg = f"failed: {e}"
            self.gpu_text = f"{'Chat' if mode == 'chat' else 'Media'}: {msg} ({datetime.now():%H:%M})"
            self.ui_queue.put(self._render_gpu)
            self.refresh_soon()

        self.gpu_text = f"Switching to {mode}..."
        self.ui_queue.put(self._render_gpu)
        threading.Thread(target=run, daemon=True).start()

    def _render_gpu(self) -> None:
        if self._window_built() and getattr(self, "gpu_label", None):
            self.gpu_label.configure(text=self.gpu_text)

    def open_url(self, svc: str) -> None:
        webbrowser.open(ui_links(self.profile)[svc])

    def open_path(self, path: Path) -> None:
        os.startfile(str(path)) if os.name == "nt" else webbrowser.open(path.as_uri())

    def open_logs(self, *_):
        self.open_path(Path(self.profile["data_dir"]) / "logs")

    def show_log(self, svc: str) -> None:
        log = self.problems.get(svc, ("", "", services.log_file(self.profile, svc)))[2]
        self.open_path(log if log.exists() else log.parent)

    def quit(self, stop_services: bool) -> None:
        def run() -> None:
            if stop_services:
                services.stop(self.profile, self.managed)
            self.stop_event.set()
            self.icon.stop()
            self.ui_queue.put(self.root.quit)

        threading.Thread(target=run, daemon=True).start()

    # ---------- tray menu ----------
    def _status_text(self, svc: str):
        def text(_item) -> str:
            row, pending = self.rows.get(svc), self.pending.get(svc)
            if pending:
                mark = "starting..." if pending[0] == "start" else "stopping..."
            elif row and row["state"] == "starting":
                mark = "◐ starting"
            elif row and row["healthy"]:
                mark = "● up"
            elif features.service_installed(svc, self.feature_status) is False:
                mark = "not installed"
            elif svc in features.NOT_INSTALLABLE and svc not in self.managed:
                mark = "not available yet"
            else:
                mark = "○ down"
            return f"{LABELS[svc]}: {mark}"

        return text

    def _menu(self) -> pystray.Menu:
        links = ui_links(prof.resolve_profile())
        return pystray.Menu(
            pystray.MenuItem("Show status", lambda *_: self.ui_queue.put(lambda: self.show_window(0)), default=True),
            pystray.MenuItem("Usage by model", lambda *_: self.ui_queue.put(lambda: self.show_window(1))),
            pystray.MenuItem("Settings", lambda *_: self.ui_queue.put(lambda: self.show_window(2))),
            pystray.MenuItem("Add features...", self.open_installer),
            pystray.Menu.SEPARATOR,
            *[pystray.MenuItem(self._status_text(s), None, enabled=False) for s in ["ollama", *services.SERVICE_ORDER]],
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Open chat (Open WebUI)", lambda *_: webbrowser.open(links["open_webui"])),
            pystray.MenuItem("Open traces (Phoenix)", lambda *_: webbrowser.open(links["phoenix"])),
            pystray.MenuItem("Open gateway admin (LiteLLM)", lambda *_: webbrowser.open(links["litellm"])),
            pystray.MenuItem("Open image studio (ComfyUI)", lambda *_: webbrowser.open(links["comfyui"])),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Voice typing button", lambda *_: self.set_dictation_button(not self.dictation_button),
                             checked=lambda _item: bool(self.dictation_button),
                             visible=lambda _item: self.dictation_button is not None),
            pystray.MenuItem("Refine button (pencil)", lambda *_: self.set_refine_button(not self.refine_button),
                             checked=lambda _item: bool(self.refine_button),
                             visible=lambda _item: self.refine_button is not None),
            pystray.MenuItem("GPU for chat (free ComfyUI's memory)", lambda *_: self.set_gpu_mode("chat")),
            pystray.MenuItem("GPU for media (unload Ollama's models)", lambda *_: self.set_gpu_mode("media")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Start all services", self.start_all),
            pystray.MenuItem("Stop all services", self.stop_all),
            pystray.MenuItem("Open logs folder", self.open_logs),
            pystray.MenuItem("Start at login", lambda *_: self._toggle_startup(), checked=lambda _item: startup.is_installed()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit (keep services running)", lambda *_: self.quit(False)),
            pystray.MenuItem("Stop services and quit", lambda *_: self.quit(True)),
        )

    def set_dictation_button(self, visible: bool) -> None:
        """Show or hide voice typing's floating mic button. The app shows or hides it at once and saves the choice
        (dictation.button), so it survives a restart; hiding it from its own menu can be undone here."""
        self.dictation_button = visible  # the window and menu follow the click at once
        self._overlay_button("show" if visible else "hide", "mic")

    def set_refine_button(self, visible: bool) -> None:
        """The same for the refine (pencil) button next to the mic (refine.button)."""
        self.refine_button = visible
        self._overlay_button("show_refine" if visible else "hide_refine", "refine")

    def _overlay_button(self, action: str, name: str) -> None:
        from stacklib.dictation import control

        self.ui_queue.put(self._render_services)  # called from the tray menu's thread too: draw on the Tk thread

        def run() -> None:
            try:
                control.call(int(self.profile["ports"]["dictation"]), action)
            except (OSError, ValueError) as e:
                print(f"[tray] could not {action} the {name} button: {e}")
            self.refresh_soon()

        threading.Thread(target=run, daemon=True).start()

    def open_installer(self, *_) -> None:
        """Add features: open the installer window in its own process (stacklib/install.launch_window), unless the one
        opened last is still open. Its features page shows what is installed and what each feature costs."""
        def run() -> None:
            from stacklib import install

            pid, started = self.installer or (0, None)
            if started is not None and services._proc_info(pid)[1] == started:   # same process, not a reused pid
                note = "The installer is already open; it may be behind another window."
            else:
                try:
                    pid = install.launch_window()
                    self.installer = (pid, services._proc_info(pid)[1])
                    note = "Opening the installer; this card updates once setup has run."
                except OSError as e:
                    note = f"Could not open the installer: {e}. Run install.cmd instead."
            print(f"[tray] {note}")

            def show() -> None:
                self.installer_note = note
                self._render_features()
            self.ui_queue.put(show)

        threading.Thread(target=run, daemon=True, name="open-installer").start()

    def _toggle_startup(self) -> None:
        startup.remove() if startup.is_installed() else startup.install()
        self.icon.update_menu()
        self.ui_queue.put(self._render_window)

    # ---------- window ----------
    def show_window(self, tab: int | None = None) -> None:
        if self.window is None or not self.window.winfo_exists():
            self._build_window()
        if tab is not None:
            self.tabs.select(tab)
        self._render_window()
        self._render_usage()
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()
        self._sample_resources()

    def _style(self) -> None:
        t = self.t = THEMES[system_theme()]
        s = ttk.Style(self.root)
        s.theme_use("clam")
        base = (FONT, 10)
        s.configure(".", background=t["page"], foreground=t["ink"], font=base, bordercolor=t["border"],
                    lightcolor=t["card"], darkcolor=t["card"], troughcolor=t["page"], focuscolor=t["accent"])
        s.configure("Card.TFrame", background=t["card"])
        s.configure("TLabel", background=t["page"], foreground=t["ink"])
        for name, fg, font in (("", t["ink"], base), ("Muted", t["muted"], (FONT, 9)), ("Sub", t["ink2"], base),
                               ("Title", t["ink"], (FONT, 11, "bold")), ("Big", t["ink"], (FONT, 18, "bold"))):
            s.configure(f"Card.{name}.TLabel" if name else "Card.TLabel", background=t["card"], foreground=fg, font=font)
        s.configure("Head.TLabel", background=t["page"], foreground=t["ink"], font=(FONT, 16, "bold"))
        s.configure("HeadSub.TLabel", background=t["page"], foreground=t["ink2"])
        s.configure("Warn.TLabel", background=t["card"], foreground=t["warn"])
        s.configure("Bad.TLabel", background=t["card"], foreground=t["bad"])
        # Keyboard focus: clam's dotted ring inside, plus a 2 px solid ring (clam draws a border only for a solid or
        # raised relief). Rings are accent on surfaces and ink or accent-ink on accent fills, 3:1 or more either way.
        s.configure("TButton", background=t["card"], foreground=t["ink"], padding=(10, 4), relief="flat", borderwidth=1)
        s.map("TButton", background=[("disabled", t["page"]), ("active", t["hover"])], foreground=[("disabled", t["muted"])],
              relief=[("focus", "solid")], bordercolor=[("focus", t["accent"])])
        s.configure("Accent.TButton", background=t["accent"], foreground=t["accent_ink"], bordercolor=t["accent"], focuscolor=t["accent_ink"])
        s.map("Accent.TButton", background=[("disabled", t["border"]), ("active", t["accent"])], bordercolor=[("focus", t["ink"])])
        s.configure("Seg.TRadiobutton", background=t["card"], foreground=t["ink2"], padding=(10, 3), indicatorrelief="flat", relief="flat")
        s.layout("Seg.TRadiobutton", [("Radiobutton.border", {"sticky": "nswe", "children": [("Radiobutton.padding", {"sticky": "nswe", "children": [
            ("Radiobutton.focus", {"sticky": "nswe", "children": [("Radiobutton.label", {"sticky": "nswe"})]})]})]})])
        s.map("Seg.TRadiobutton", background=[("selected", t["accent"]), ("active", t["hover"])], foreground=[("selected", t["accent_ink"])],
              relief=[("focus", "solid")], bordercolor=[("focus", "selected", t["ink"]), ("focus", t["accent"])],
              focuscolor=[("selected", t["accent_ink"])])
        for w in ("TCheckbutton",):
            s.configure(w, background=t["card"], foreground=t["ink"], indicatorbackground=t["card"], indicatorforeground=t["accent"], relief="flat")
            s.layout(w, [("Checkbutton.border", {"sticky": "nswe", "children": [("Checkbutton.padding", {"sticky": "nswe", "children": [
                ("Checkbutton.indicator", {"side": "left", "sticky": ""}),
                ("Checkbutton.focus", {"side": "left", "sticky": "w", "children": [("Checkbutton.label", {"sticky": "nswe"})]})]})]})])
            s.map(w, background=[("active", t["card"])], indicatorbackground=[("selected", t["card"])],
                  relief=[("focus", "solid")], bordercolor=[("focus", t["accent"])])
        s.configure("Page.TCheckbutton", background=t["page"])
        s.map("Page.TCheckbutton", background=[("active", t["page"])])
        s.configure("TCombobox", fieldbackground=t["card"], background=t["card"], foreground=t["ink"], arrowcolor=t["ink2"], padding=3)
        # The field draws bordercolor outside and lightcolor inside: both on focus make the 2 px ring, since these
        # maps hide clam's own cue for a focused read-only box (its selected text).
        s.map("TCombobox", fieldbackground=[("readonly", t["card"])], foreground=[("readonly", t["ink"])],
              selectbackground=[("readonly", t["card"])], selectforeground=[("readonly", t["ink"])],
              bordercolor=[("focus", t["accent"])], lightcolor=[("focus", t["accent"])])
        self.root.option_add("*TCombobox*Listbox.background", t["card"])
        self.root.option_add("*TCombobox*Listbox.foreground", t["ink"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", t["select"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", t["ink"])
        s.configure("TNotebook", background=t["page"], borderwidth=0, tabmargins=(0, 0, 0, 0))
        s.configure("TNotebook.Tab", background=t["page"], foreground=t["ink2"], padding=(16, 7), borderwidth=0, font=(FONT, 10))
        s.map("TNotebook.Tab", background=[("selected", t["card"])], foreground=[("selected", t["ink"])],
              lightcolor=[("focus", "selected", t["accent"]), ("selected", t["card"])],
              bordercolor=[("focus", "selected", t["accent"]), ("selected", t["border"])], expand=[("selected", (0, 0, 0, 0))])
        s.configure("Treeview", background=t["card"], fieldbackground=t["card"], foreground=t["ink"], rowheight=26, borderwidth=0)
        s.map("Treeview", background=[("selected", t["select"])], foreground=[("selected", t["ink"])])
        s.configure("Treeview.Heading", background=t["card"], foreground=t["ink2"], relief="flat", font=(FONT, 9, "bold"), padding=(6, 4))
        s.map("Treeview.Heading", background=[("active", t["hover"])])
        s.configure("Vertical.TScrollbar", background=t["card"], troughcolor=t["page"], arrowcolor=t["ink2"], bordercolor=t["page"])

    def _card(self, parent, title: str | None = None, **grid) -> ttk.Frame:
        outer = tk.Frame(parent, bg=self.t["border"], padx=1, pady=1)
        outer.grid(sticky="nsew", **grid)
        inner = ttk.Frame(outer, style="Card.TFrame", padding=14)
        inner.pack(fill="both", expand=True)
        if title:
            ttk.Label(inner, text=title, style="Card.Title.TLabel").grid(row=0, column=0, columnspan=10, sticky="w", pady=(0, 8))
        return inner

    def _scroll_area(self, tab, parent, bg: str, **frame) -> tuple[tk.Frame, ttk.Frame]:
        """A vertically scrolling frame for tab content that can be taller than the window. Returns (holder to place,
        frame to fill). The scrollbar shows only while the content does not fit; the wheel scrolls it while `tab` is
        the current tab (see _wheel)."""
        holder = tk.Frame(parent, bg=bg)
        canvas = tk.Canvas(holder, bg=bg, highlightthickness=0, height=1)
        sb = ttk.Scrollbar(holder, orient="vertical", command=canvas.yview)

        def yset(first, last) -> None:
            if float(first) <= 0 and float(last) >= 1:
                sb.pack_forget()
            elif not sb.winfo_manager():
                sb.pack(side="right", fill="y", before=canvas)
            sb.set(first, last)

        canvas.configure(yscrollcommand=yset)
        canvas.pack(side="left", fill="both", expand=True)
        inner = ttk.Frame(canvas, **frame)
        win = canvas.create_window(0, 0, window=inner, anchor="nw")
        inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        self.scroll_canvases[str(tab)] = canvas
        return holder, inner

    def _wheel(self, e) -> None:
        """Scroll the current tab's scroll area, if it has one. Windows sends 120 per notch; touchpads and macOS send
        smaller steps, which still scroll one unit instead of rounding to none."""
        canvas = self.scroll_canvases.get(self.tabs.select())
        if canvas is None:
            return
        if e.num in (4, 5):
            units = -1 if e.num == 4 else 1
        elif e.delta:
            units = -round(e.delta / 120) or (-1 if e.delta > 0 else 1)
        else:
            return
        canvas.yview_scroll(units, "units")

    def _build_window(self) -> None:
        self._style()
        t = self.t
        w = tk.Toplevel(self.root, bg=t["page"])
        w.title("Agent Stack")
        w.geometry(f"940x{min(900, w.winfo_screenheight() - 80)}")  # Overview scrolls: services, GPU, features, HF cache
        w.minsize(760, 560)
        w.protocol("WM_DELETE_WINDOW", w.withdraw)  # closing hides it; the tray keeps running
        if IS_WINDOWS and system_theme() == "dark":
            try:  # dark title bar (DWMWA_USE_IMMERSIVE_DARK_MODE)
                import ctypes

                w.update_idletasks()
                hwnd = ctypes.windll.user32.GetParent(w.winfo_id())
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(ctypes.c_int(1)), 4)
            except (OSError, AttributeError):
                pass
        self.window = w
        w.bind("<Map>", lambda e: self._sample_resources() if e.widget is w else None)  # restored from the taskbar

        head = ttk.Frame(w, padding=(18, 14, 18, 8))
        head.pack(fill="x")
        ttk.Label(head, text="Agent Stack", style="Head.TLabel").grid(row=0, column=0, sticky="w")
        self.head_sub = ttk.Label(head, text="", style="HeadSub.TLabel")
        self.head_sub.grid(row=1, column=0, sticky="w")
        head.columnconfigure(0, weight=1)
        pill = tk.Frame(head, bg=t["card"], highlightbackground=t["border"], highlightthickness=1)
        pill.grid(row=0, column=1, rowspan=2, sticky="e")
        self.pill_dot = tk.Label(pill, text="●", bg=t["card"], font=(FONT, 12))
        self.pill_dot.pack(side="left", padx=(10, 4), pady=4)
        self.pill_text = tk.Label(pill, text="", bg=t["card"], fg=t["ink"], font=(FONT, 10))
        self.pill_text.pack(side="left", padx=(0, 12))

        self.tabs = ttk.Notebook(w)
        self.tabs.pack(fill="both", expand=True, padx=18, pady=(4, 18))
        self.tabs.bind("<<NotebookTabChanged>>", lambda _e: (self._render_usage(), self._sample_resources()))
        self.scroll_canvases: dict[str, tk.Canvas] = {}
        # Tk 8.6 on X11 reports the wheel as buttons 4 and 5 (on Windows those are the side buttons).
        wheel = ["<MouseWheel>", *(["<Button-4>", "<Button-5>"] if self.root.tk.call("tk", "windowingsystem") == "x11" else [])]
        for seq in wheel:
            w.bind_all(seq, self._wheel, add="+")
            # Tk's own TCombobox binding steps a read-only box to the next value; scroll the tab instead and stop
            # there, so the "all" binding above does not scroll a second time.
            self.root.bind_class("TCombobox", seq, lambda e: (self._wheel(e), "break")[1])
            # A settings text box scrolls its own text first (Tk's Text binding); the tab scrolls only while the
            # whole text is in view, so the wheel never moves both at once.
            self.root.bind_class("SettingText", seq, lambda e: "break" if e.widget.yview() != (0.0, 1.0) else None)
        self._build_overview(ttk.Frame(self.tabs, padding=(0, 12, 0, 0)))
        self._build_usage(ttk.Frame(self.tabs, padding=(0, 12, 0, 0)))
        self._build_settings(ttk.Frame(self.tabs, padding=(0, 12, 0, 0)))
        self._build_resources(ttk.Frame(self.tabs, padding=(0, 12, 0, 0)))

    # ---------- Overview tab ----------
    def _build_overview(self, tab: ttk.Frame) -> None:
        self.tabs.add(tab, text="Overview")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)
        # The cards scroll when the window is shorter than they are; the action bar below stays in view.
        holder, body = self._scroll_area(tab, tab, self.t["page"])
        holder.grid(row=0, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        card = self._card(body, "Services", row=0, column=0)
        card.columnconfigure(1, weight=1)
        self.row_widgets: dict[str, tuple] = {}
        self.reason_widgets: dict[str, tuple] = {}
        links = ui_links(self.profile)
        for n, svc in enumerate(["ollama", *services.SERVICE_ORDER]):
            i = 2 * n + 1  # each service has a second grid row for the reason a start or stop failed
            dot = tk.Label(card, text="●", font=(FONT, 12), bg=self.t["card"])
            dot.grid(row=i, column=0, padx=(0, 10), pady=5)
            names = ttk.Frame(card, style="Card.TFrame")
            names.grid(row=i, column=1, sticky="w")
            ttk.Label(names, text=LABELS[svc], style="Card.TLabel", font=(FONT, 10, "bold")).pack(anchor="w")
            ttk.Label(names, text=f"{ROLES[svc]}  ·  port {self.profile['ports'][svc]}", style="Card.Muted.TLabel").pack(anchor="w")
            state = ttk.Label(card, text="", style="Card.Sub.TLabel", width=-18)  # at least 18 characters, grows to fit
            state.grid(row=i, column=2, sticky="w", padx=8)
            buttons = ttk.Frame(card, style="Card.TFrame")
            buttons.grid(row=i, column=3, sticky="e")
            if svc in links:
                ttk.Button(buttons, text="Open", width=7, command=lambda s=svc: self.open_url(s)).pack(side="left", padx=2)
            if svc == "dictation":
                # Bring back (or hide) the floating mic and refine buttons without opening Settings.
                self.dictation_btn = ttk.Button(buttons, text="Hide mic", width=11,
                                                command=lambda: self.set_dictation_button(not self.dictation_button))
                self.dictation_btn.pack(side="left", padx=2)
                self.refine_btn = ttk.Button(buttons, text="Hide pencil", width=11,
                                             command=lambda: self.set_refine_button(not self.refine_button))
                self.refine_btn.pack(side="left", padx=2)
            toggle = ttk.Button(buttons, text="Stop", width=7, command=lambda s=svc: self.toggle(s))
            if svc != "ollama":
                toggle.pack(side="left", padx=2)
            self.row_widgets[svc] = (dot, state, toggle)
            reason = ttk.Label(card, text="", style="Bad.TLabel", wraplength=560, justify="left")
            reason.grid(row=i + 1, column=1, columnspan=2, sticky="w", pady=(0, 6))
            show = ttk.Button(card, text="Show log", width=9, command=lambda s=svc: self.show_log(s))
            show.grid(row=i + 1, column=3, sticky="e", padx=2, pady=(0, 6))
            reason.grid_remove()
            show.grid_remove()
            self.reason_widgets[svc] = (reason, show)

        # One card for the GPU: what Ollama holds, and the switch that hands the card to chat or to media (plan G1).
        models = self._card(body, "GPU: loaded in Ollama", row=1, column=0, pady=(12, 0))
        models.columnconfigure(0, weight=1)
        self.loaded_frame = ttk.Frame(models, style="Card.TFrame")
        self.loaded_frame.grid(row=1, column=0, columnspan=2, sticky="we")
        self.gpu_text = getattr(self, "gpu_text", "Chat and media share the card: Media before long image or video "
                                "jobs, Chat for fast replies.")
        self.gpu_label = ttk.Label(models, text=self.gpu_text, style="Card.Muted.TLabel", wraplength=640, justify="left")
        self.gpu_label.grid(row=2, column=0, sticky="w", pady=(6, 0))
        gbtn = ttk.Frame(models, style="Card.TFrame")
        gbtn.grid(row=2, column=1, sticky="e", pady=(6, 0))
        ttk.Button(gbtn, text="Chat", width=7, command=lambda: self.set_gpu_mode("chat")).pack(side="left", padx=2)
        ttk.Button(gbtn, text="Media", width=7, command=lambda: self.set_gpu_mode("media")).pack(side="left", padx=2)

        # The installer's features: installed, on or off, linked to the stack, and what each takes on this PC.
        feats = self._card(body, "Features", row=2, column=0, pady=(12, 0))
        feats.columnconfigure(1, weight=1)
        self.feature_widgets: dict[str, tuple] = {}
        for n, f in enumerate(features.FEATURES):
            i = 2 * n + 1
            dot = tk.Label(feats, text="●", font=(FONT, 12), bg=self.t["card"], fg=self.t["muted"])
            dot.grid(row=i, column=0, padx=(0, 10), pady=(5, 0), sticky="n")
            names = ttk.Frame(feats, style="Card.TFrame")
            names.grid(row=i, column=1, sticky="w")
            ttk.Label(names, text=f.title, style="Card.TLabel", font=(FONT, 10, "bold")).pack(anchor="w")
            load = ttk.Label(names, text="", style="Card.Muted.TLabel")
            load.pack(anchor="w")
            state = ttk.Label(feats, text="Checking...", style="Card.Sub.TLabel", width=-18)
            state.grid(row=i, column=2, sticky="w", padx=8)
            detail = ttk.Label(feats, text="", style="Card.Muted.TLabel", wraplength=640, justify="left")
            detail.grid(row=i + 1, column=1, columnspan=2, sticky="w", pady=(0, 6))
            fix = None
            if f.id == "openclaw":
                fix = ttk.Button(feats, text="Use gateway", command=self.openclaw_use_gateway)
                fix.grid(row=i, column=3, sticky="e", padx=2)
                fix.grid_remove()
            self.feature_widgets[f.id] = (dot, load, state, detail, fix)
        foot = ttk.Frame(feats, style="Card.TFrame")
        foot.grid(row=2 * len(features.FEATURES) + 1, column=0, columnspan=4, sticky="we", pady=(4, 0))
        foot.columnconfigure(0, weight=1)
        self.features_note = ttk.Label(foot, text="", style="Card.Muted.TLabel", wraplength=640, justify="left")
        self.features_note.grid(row=0, column=0, sticky="w")
        self.add_features_btn = ttk.Button(foot, text="Add features...", command=self.open_installer)
        self.add_features_btn.grid(row=0, column=1, sticky="e", padx=(8, 2))

        extras = self._card(body, "Hugging Face cache", row=3, column=0, pady=(12, 0))
        extras.columnconfigure(1, weight=1)
        self.client_widgets: dict[str, tuple] = {}
        for n, (key, label, role) in enumerate(CLIENTS):
            i = 2 * n + 1
            dot = tk.Label(extras, text="●", font=(FONT, 12), bg=self.t["card"])
            dot.grid(row=i, column=0, padx=(0, 10), pady=(5, 0), sticky="n")
            names = ttk.Frame(extras, style="Card.TFrame")
            names.grid(row=i, column=1, sticky="w")
            ttk.Label(names, text=label, style="Card.TLabel", font=(FONT, 10, "bold")).pack(anchor="w")
            ttk.Label(names, text=role, style="Card.Muted.TLabel").pack(anchor="w")
            state = ttk.Label(extras, text="Checking...", style="Card.Sub.TLabel", width=-18)
            state.grid(row=i, column=2, sticky="w", padx=8)
            detail = ttk.Label(extras, text="", style="Card.Muted.TLabel", wraplength=640, justify="left")
            detail.grid(row=i + 1, column=1, columnspan=2, sticky="w", pady=(0, 6))
            self.client_widgets[key] = (dot, state, detail)

        bar = ttk.Frame(tab, padding=(0, 12, 0, 0))
        bar.grid(row=1, column=0, sticky="we")
        ttk.Button(bar, text="Open chat", style="Accent.TButton", command=lambda: self.open_url("open_webui")).pack(side="left")
        self.start_btn = ttk.Button(bar, text="Start all", command=self.start_all)
        self.start_btn.pack(side="left", padx=(8, 4))
        self.stop_btn = ttk.Button(bar, text="Stop all", command=self.stop_all)
        self.stop_btn.pack(side="left")
        ttk.Button(bar, text="Logs", command=self.open_logs).pack(side="left", padx=4)
        self.startup_var = tk.BooleanVar(value=startup.is_installed())
        ttk.Checkbutton(bar, text="Start at login", style="Page.TCheckbutton", variable=self.startup_var,
                        command=self._toggle_startup).pack(side="right")

    def _window_built(self) -> bool:
        return self.window is not None and self.window.winfo_exists()

    def _created(self, pid: int | None) -> float | None:
        """When a service process was created (epoch seconds), cached per pid."""
        if pid and pid not in self.created:
            try:
                self.created[pid] = psutil.Process(pid).create_time()
            except (psutil.Error, OSError):
                return None
        return self.created.get(pid) if pid else None

    def _render_window(self) -> None:
        if not self._window_built():
            return
        self._render_services()
        m = self.profile["models"]
        cloud = "external models allowed" if self.profile["policy"]["external"]["enabled"] else "private only"
        self.head_sub.configure(text=f"{self.profile['name']}  ·  primary {m.get('primary')} @ {compact(m.get('primary_num_ctx', 0))} ctx  ·  {cloud}")
        self.startup_var.set(startup.is_installed())
        self._render_loaded()
        self._render_clients()
        self._render_features()
        if any(r["state"] == "starting" for r in self.rows.values()):
            self._tick_soon()

    def _render_services(self) -> None:
        """Service rows, the status pill and Start all / Stop all, from cached state only (no I/O): runs on every
        click and once a second while something is starting or stopping."""
        if not self._window_built():
            return
        t = self.t
        up = 0
        for svc, (dot, state, toggle) in self.row_widgets.items():
            row = self.rows.get(svc, {})
            healthy = bool(row.get("healthy"))
            enabled = svc == "ollama" or svc in self.managed
            up += healthy and enabled
            pid = row.get("pid")
            pending = self.pending.get(svc)
            installed = features.service_installed(svc, self.feature_status)  # None until the first feature check
            if pending:
                dot.configure(fg=t["warn"])
                verb = "Starting" if pending[0] == "start" else "Stopping"
                state.configure(text=verb + waited(time.monotonic() - pending[1]), style="Warn.TLabel")
            elif healthy:
                dot.configure(fg=t["good"])
                state.configure(text=f"Running{f'  (pid {pid})' if pid else ''}", style="Card.Sub.TLabel")
            elif row.get("state") == "starting":  # the process is alive but does not answer yet
                created = self._created(pid)
                dot.configure(fg=t["warn"])
                state.configure(text="Starting" + waited(created and time.time() - created), style="Warn.TLabel")
            elif installed is False:  # its feature was not installed: Start would only fail
                dot.configure(fg=t["warn"] if enabled else t["muted"])
                state.configure(text="Not installed", style="Warn.TLabel" if enabled else "Card.Sub.TLabel")
            elif enabled:
                dot.configure(fg=t["bad"])
                state.configure(text="Stopped", style="Card.Sub.TLabel")
            elif svc in features.NOT_INSTALLABLE:
                dot.configure(fg=t["muted"])
                state.configure(text="Not available yet", style="Card.Sub.TLabel")
            else:
                dot.configure(fg=t["muted"])
                state.configure(text="Off in settings", style="Card.Sub.TLabel")
            stopping = bool(pending) and pending[0] == "stop"
            startable = (enabled and installed is not False) or healthy or self._running(svc)
            toggle.configure(text="Stop" if self._running(svc) else "Start",
                             state="disabled" if self.busy or stopping or not startable else "normal")
            problem = self.problems.get(svc)
            if problem and (problem[0] == "start") == healthy:
                del self.problems[svc]  # it came up (or went down) after all
                problem = None
            reason, show = self.reason_widgets[svc]
            if problem and not pending:
                reason.configure(text=problem[1])
                reason.grid()
                show.grid()
            else:
                reason.grid_remove()
                show.grid_remove()
        for attr, shown, name in (("dictation_btn", self.dictation_button, "mic"),
                                  ("refine_btn", self.refine_button, "pencil")):
            btn = getattr(self, attr, None)
            if btn is None:
                continue
            if shown is None:
                btn.configure(text=f"Show {name}", state="disabled")
            else:
                btn.configure(text=f"Hide {name}" if shown else f"Show {name}", state="normal")
        total = sum(1 for s in self.row_widgets if s == "ollama" or s in self.managed)
        self.pill_dot.configure(fg=t["good"] if up == total else (t["warn"] if up else t["bad"]))
        activity = self._activity()
        busy = f"  ·  {activity}..." if activity else ""
        self.pill_text.configure(text=f"{up}/{total} running  ·  checked {self.checked_at or '...'}{busy}")
        can_start = any(not self._running(s) and s not in self.pending for s in self.managed)
        can_stop = any(self._running(s) and self.pending.get(s, ("",))[0] != "stop" for s in self.managed)
        self.start_btn.configure(state="normal" if can_start and not self.busy else "disabled")
        self.stop_btn.configure(state="normal" if can_stop and not self.busy else "disabled")

    def _level_look(self, level: str) -> tuple[str, str]:
        """(dot colour, state label style) for a status level: ok, warn, bad or off."""
        t = self.t
        return ({"ok": t["good"], "warn": t["warn"], "bad": t["bad"]}.get(level, t["muted"]),
                {"warn": "Warn.TLabel", "bad": "Bad.TLabel"}.get(level, "Card.Sub.TLabel"))

    def _render_clients(self) -> None:
        for key, (dot, state, detail) in self.client_widgets.items():
            s = self.client_status.get(key)
            if s:
                fg, style = self._level_look(s.level)
                dot.configure(fg=fg)
                state.configure(text=s.state, style=style)
                detail.configure(text=s.detail)

    def _render_features(self) -> None:
        """The Features card, from the last feature check (once a minute) and OpenClaw's Use gateway state."""
        if not self._window_built() or not hasattr(self, "feature_widgets"):
            return
        status = self.feature_status
        for fid, (dot, load, state, detail, fix) in self.feature_widgets.items():
            f, s, e = features.BY_ID[fid], status.get(fid), self.feature_est.get(fid)
            if e:
                load.configure(text=("Required  ·  " if f.required else "") + features.brief(e))
            if fid == "openclaw" and self.openclaw_busy:
                dot.configure(fg=self.t["warn"])
                state.configure(text="Setting up...", style="Warn.TLabel")
            elif s:
                fg, style = self._level_look(s.level)
                dot.configure(fg=fg)
                state.configure(text=s.state, style=style)
                detail.configure(text=(self.openclaw_result + "  " if fid == "openclaw" and self.openclaw_result else "")
                                 + s.detail)
            if fix is not None:
                # Shown while OpenClaw is installed but not gateway-only; a failure keeps it up so the owner can retry.
                if self.openclaw_busy or (s and s.installed and not s.on and s.state != "Not checked"):
                    fix.configure(state="disabled" if self.openclaw_busy else "normal")
                    fix.grid()
                else:
                    fix.grid_remove()
        missing = [features.BY_ID[fid].short for fid in features.not_installed(status)]
        if not status:
            note = "Checking which features are installed..."
        elif missing:
            note = (f"Not installed: {', '.join(missing)}. Add features opens the installer, which shows what each one "
                    "takes on this PC; installed features stay as they are.")
        else:
            note = "Every feature is installed. The installer checks and repairs them; Settings turns them off."
        self.features_note.configure(text=f"{self.installer_note}  {note}" if self.installer_note else note)
        self.add_features_btn.configure(text="Add features..." if missing or not status else "Open installer...")

    def openclaw_use_gateway(self) -> None:
        """Onboard OpenClaw if needed and make the gateway its only model endpoint (clients.setup_openclaw). No
        confirmation: the button says what it does and OpenClaw keeps the replaced config as openclaw.json.bak."""
        if self.openclaw_busy:
            return
        self.openclaw_busy = True
        self.openclaw_result = ""
        self._render_features()

        def run() -> None:
            try:
                result = clients.setup_openclaw(self.profile, lambda m: print(f"[tray] openclaw: {m}"))
            except Exception as e:  # noqa: BLE001 - shown on the row; the log has the trace
                traceback.print_exc()
                result = f"Use gateway failed: {e}"
            self.client_status = self._check_clients()
            self._check_features()

            def done() -> None:
                self.openclaw_busy = False
                self.openclaw_result = result if result.startswith("Use gateway failed") else ""
                self._render_clients()
                self._render_features()
            self._on_ui(done)
        threading.Thread(target=run, daemon=True, name="openclaw-setup").start()

    def _render_loaded(self) -> None:
        for child in self.loaded_frame.winfo_children():
            child.destroy()
        if not self.loaded:
            ttk.Label(self.loaded_frame, text="No model is loaded. The first request loads one (this can take a minute or two).",
                      style="Card.Muted.TLabel").grid(row=0, column=0, sticky="w")
            return
        for c, h in enumerate(("Model", "Size", "On GPU", "Context", "Unloads")):
            ttk.Label(self.loaded_frame, text=h, style="Card.Muted.TLabel").grid(row=0, column=c, sticky="w", padx=(0, 24))
        for r, m in enumerate(self.loaded, start=1):
            size, vram = int(m.get("size") or 0), int(m.get("size_vram") or 0)
            gpu = f"{100 * vram / size:.0f}%" if size else "-"
            try:
                exp = datetime.fromisoformat(m["expires_at"])
                left = (exp - datetime.now(timezone.utc)).total_seconds()
                unloads = "never" if left > 86400 * 365 else (f"in {int(left // 60)} min" if left > 0 else "soon")
            except (KeyError, ValueError, TypeError):
                unloads = "-"
            vals = (m.get("name", "?"), human_bytes(size), gpu, compact(m.get("context_length") or 0), unloads)
            for c, v in enumerate(vals):
                ttk.Label(self.loaded_frame, text=v, style="Card.TLabel").grid(row=r, column=c, sticky="w", padx=(0, 24), pady=2)

    # ---------- Resources tab ----------
    def _build_resources(self, tab: ttk.Frame) -> None:
        self.tabs.add(tab, text="Resources")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)
        card = self._card(tab, "Live process resources", row=0, column=0)
        card.columnconfigure(0, weight=1)
        card.rowconfigure(2, weight=1)
        ttk.Label(card, text=f"CPU is the share of all {process_metrics.CPU_COUNT} logical processors (100% is the whole machine), "
                  "measured since the previous sample; GPU metrics are reported by the driver. Unavailable readings show as -.",
                  style="Card.Muted.TLabel", wraplength=820, justify="left").grid(row=1, column=0, sticky="w", pady=(0, 8))
        cols = (("name", "Process", 260, "w"), ("pid", "PID", 80, "e"), ("cpu", "CPU % (all cores)", 130, "e"),
                ("memory", "RAM MB", 100, "e"), ("gpu", "GPU engine %", 120, "e"), ("gpu_memory", "GPU dedicated MB", 150, "e"))
        self.process_tree = ttk.Treeview(card, columns=[c[0] for c in cols], show="headings", height=16)
        for key, title, width, anchor in cols:
            self.process_tree.heading(key, text=title)
            self.process_tree.column(key, width=width, minwidth=60, anchor=anchor)
        scroll = ttk.Scrollbar(card, orient="vertical", command=self.process_tree.yview)
        self.process_tree.configure(yscrollcommand=scroll.set)
        self.process_tree.grid(row=2, column=0, sticky="nsew")
        scroll.grid(row=2, column=1, sticky="ns")
        self.resources_note = ttk.Label(card, text="Reading processes...", style="Card.Muted.TLabel")
        self.resources_note.grid(row=3, column=0, sticky="w", pady=(8, 0))

    def _resources_visible(self) -> bool:
        w = self.window
        return bool(w is not None and w.winfo_exists() and w.state() == "normal" and self.tabs.index("current") == RESOURCES_TAB)

    def _sample_resources(self) -> None:
        """Sample processes while the Resources tab is on screen. A sample takes about 3 s (the GPU counters start
        PowerShell), so it runs off the Tk thread, one at a time, and never holds up the status poll."""
        if self.sample_job:
            self.root.after_cancel(self.sample_job)
            self.sample_job = None
        if self.sampling or not self._resources_visible():
            return
        self.sampling = True

        def run() -> None:
            try:
                rows, error = self.process_sampler.sample(), ""
            except Exception as e:  # noqa: BLE001 - shown in the tab and retried with backoff
                rows, error = [], str(e)
            self.ui_queue.put(lambda: self._resources_sampled(rows, error))

        threading.Thread(target=run, daemon=True).start()

    def _resources_sampled(self, rows: list[dict], error: str) -> None:
        self.sampling = False
        if self.window is None or not self.window.winfo_exists():
            return
        if error:
            self.sample_failures += 1
            wait = min(300, RESOURCE_SECONDS * 2 ** self.sample_failures)
            print(f"[tray] process sample failed: {error}")
            note = f"Could not read the process list: {error}. Next try in {wait} s."
        else:
            self.sample_failures, wait = 0, RESOURCE_SECONDS
            self.process_rows = rows
            self._render_resources()
            gpu = self.process_sampler.gpu_problem
            note = f"GPU columns are empty: {gpu}." if gpu else f"Updated {datetime.now():%H:%M:%S}, every {RESOURCE_SECONDS} s while this tab is open."
        self.resources_note.configure(text=note)
        self.sample_job = self.root.after(wait * 1000, self._sample_resources)

    def _render_resources(self) -> None:
        """Update the rows in place, keyed by pid, so the selection and the scroll position survive each sample."""
        def num(v: float | None) -> str:
            return f"{v:.1f}" if v is not None else "-"

        tree = self.process_tree
        rows = {str(r["pid"]): r for r in self.process_rows}
        gone = [iid for iid in tree.get_children() if iid not in rows]
        if gone:
            tree.delete(*gone)
        for index, (iid, r) in enumerate(rows.items()):
            values = (r["name"], r["pid"], num(r["cpu_percent"]), num(r["memory_mb"]), num(r["gpu_percent"]), num(r["gpu_memory_mb"]))
            if tree.exists(iid):
                tree.item(iid, values=values)
                tree.move(iid, "", index)
            else:
                tree.insert("", index, iid=iid, values=values)

    # ---------- Usage tab ----------
    def _build_usage(self, tab: ttk.Frame) -> None:
        self.tabs.add(tab, text="Usage")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)
        tools = self._card(tab, row=0, column=0)
        self.range_var = tk.IntVar(value=self.usage_days)
        self.group_var = tk.StringVar(value=self.usage_group)
        ttk.Label(tools, text="Period", style="Card.Muted.TLabel").pack(side="left", padx=(0, 6))
        for label, days in RANGES:
            ttk.Radiobutton(tools, text=label, value=days, variable=self.range_var, style="Seg.TRadiobutton",
                            command=self._usage_changed).pack(side="left")
        ttk.Label(tools, text="Group by", style="Card.Muted.TLabel").pack(side="left", padx=(24, 6))
        for label, val in (("Model", "served"), ("Alias or service", "alias"), ("Client", "client")):
            ttk.Radiobutton(tools, text=label, value=val, variable=self.group_var, style="Seg.TRadiobutton",
                            command=self._usage_changed).pack(side="left")
        self.cost_note = ttk.Label(tools, text="", style="Card.Muted.TLabel")
        self.cost_note.pack(side="right")

        tiles = ttk.Frame(tab)
        tiles.grid(row=1, column=0, sticky="we", pady=(12, 0))
        self.tile_values: dict[str, ttk.Label] = {}
        for i, (key, label) in enumerate((("requests", "Requests"), ("tokens", "Tokens in / out"),
                                          ("audio", "Speech audio"), ("images", "Images"), ("errors", "Errors"),
                                          ("cost", "API cost"))):
            tiles.columnconfigure(i, weight=1, uniform="tile")
            card = self._card(tiles, row=0, column=i, padx=(0 if i == 0 else 6, 0))
            ttk.Label(card, text=label, style="Card.Muted.TLabel").pack(anchor="w")
            self.tile_values[key] = ttk.Label(card, text="-", style="Card.Big.TLabel")
            self.tile_values[key].pack(anchor="w")

        body = ttk.Frame(tab)
        body.grid(row=2, column=0, sticky="nsew", pady=(12, 0))
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=3)
        body.rowconfigure(1, weight=2)
        table = self._card(body, row=0, column=0)
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)
        # Each row expands into one row per client (per alias or service when grouped by client). Input, output and
        # the speeds are in the units of the row's kind (usage.cells): tokens, seconds of audio, or images.
        cols = [("requests", "Requests", 70, "e"), ("errors", "Errors", 50, "e"),
                ("input", "Input", 80, "e"), ("output", "Output", 80, "e"),
                ("avg_latency_ms", "Avg time", 70, "e"), ("speed", "Speed", 80, "e"),
                ("overall", "Overall", 80, "e"), ("cost", "Cost", 60, "e"), ("last", "Last used", 80, "e")]
        self.usage_sort = ("requests", True)
        self.tree = ttk.Treeview(table, columns=[c[0] for c in cols], show="tree headings", selectmode="browse", height=6)
        self.tree.heading("#0", text="Model", anchor="w", command=lambda: self._sort_usage("model"))
        self.tree.column("#0", width=170, minwidth=130, anchor="w", stretch=True)
        for key, label, width, anchor in cols:
            self.tree.heading(key, text=label, anchor=anchor, command=lambda k=key: self._sort_usage(k))
            self.tree.column(key, width=width, anchor=anchor, stretch=False)
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: (self._draw_chart(), self._render_breakdown()))
        self.tree.tag_configure("err", foreground=self.t["bad"])
        self.tree.tag_configure("sub", foreground=self.t["muted"])
        self.usage_empty = ttk.Label(table, text="", style="Card.Muted.TLabel", wraplength=640, justify="left")
        # Where the time went for the selected row (or all requests): the model's own timings versus the rest.
        self.breakdown = ttk.Label(table, text="", style="Card.Muted.TLabel", wraplength=820, justify="left")
        self.breakdown.grid(row=2, column=0, columnspan=2, sticky="we", pady=(8, 0))
        ttk.Label(table, text="Speed is the model's own pace: tokens per second while generating, seconds of audio per "
                              "second for speech, seconds per image. Overall adds loading and waiting in the queue.",
                  style="Card.Muted.TLabel", wraplength=820, justify="left").grid(row=3, column=0, columnspan=2,
                                                                                  sticky="we", pady=(4, 0))
        # Model use the tab cannot count (Open WebUI's own speech-to-text, ...), while it can happen.
        self.usage_gaps = ttk.Label(table, text="", style="Card.Muted.TLabel", wraplength=820, justify="left")

        chart = self._card(body, row=1, column=0, pady=(12, 0))
        chart.columnconfigure(0, weight=1)
        chart.rowconfigure(1, weight=1)
        self.chart_title = ttk.Label(chart, text="", style="Card.Title.TLabel")
        self.chart_title.grid(row=0, column=0, sticky="w")
        self.canvas = tk.Canvas(chart, bg=self.t["card"], highlightthickness=0, height=150)
        self.canvas.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        self.canvas.bind("<Configure>", lambda _e: self._draw_chart())
        self.canvas.bind("<Motion>", self._chart_hover)
        self.canvas.bind("<Leave>", lambda _e: self.canvas.delete("tip"))
        self.bars: list[tuple[float, float, str]] = []

    def _usage_changed(self) -> None:
        self.usage_days = self.range_var.get()
        self.usage_group = self.group_var.get()
        threading.Thread(target=self.refresh_usage, daemon=True).start()

    def _sort_usage(self, key: str) -> None:
        cur, rev = self.usage_sort
        self.usage_sort = (key, not rev if cur == key else key != "model")
        self._render_usage()

    def _render_usage(self) -> None:
        if self.window is None or not self.window.winfo_exists() or self.usage_data is None:
            return
        data = self.usage_data
        tot = data["totals"]
        tiles = {"requests": f"{tot['requests']:,}",
                 "tokens": f"{compact(tot['prompt_tokens'])} / {compact(tot['completion_tokens'])}",
                 "audio": usage.duration(tot["audio_s"]) if tot["audio_s"] else "-",
                 "images": f"{tot['images']:,}" if tot["images"] else "-",
                 "errors": f"{tot['errors']:,}", "cost": f"${tot['cost']:.2f}"}
        for key, label in self.tile_values.items():
            label.configure(text=tiles[key])
        self.tile_values["errors"].configure(foreground=self.t["bad"] if tot["errors"] else self.t["ink"])
        self.cost_note.configure(text="Local models cost $0; cost is outside-API spend.")
        selected = self.tree.selection()
        keep = selected[0] if selected else None
        self.tree.heading("#0", text={"client": "Client", "alias": "Alias or service"}.get(self.usage_group, "Model"))
        open_rows = {i for i in self.tree.get_children() if self.tree.item(i, "open")}
        self.tree.delete(*self.tree.get_children())
        key, rev = self.usage_sort
        rows = data["models"]

        def order(items: list[dict]) -> list[dict]:
            if key == "model":
                return sorted(items, key=lambda m: m["model"].lower(), reverse=rev)
            return sorted(items, key=lambda m: usage.sort_value(m, key), reverse=rev)

        def values(m: dict) -> tuple:
            c = usage.cells(m)
            return (f"{m['requests']:,}", m["errors"] or "", c["input"], c["output"],
                    f"{m['avg_latency_ms'] / 1000:.1f} s", c["speed"], c["overall"],
                    f"${m['cost']:.4f}" if m["cost"] else "-", usage.ago(m["last"]))

        def name(m: dict) -> str:  # outside APIs and confidential VMs say so; local is the default
            where = usage.LOCATION_NAMES.get(m["location"]) if m["location"] != "local" else ""
            return f"{m['model']}  ·  {where}" if where else m["model"]

        for m in order(rows):
            err = ("err",) if m["errors"] and m["errors"] == m["requests"] else ()
            self.tree.insert("", "end", iid=m["model"], text=name(m), tags=err, values=values(m),
                             open=m["model"] in open_rows)
            for c in order(m["clients"]):
                self.tree.insert(m["model"], "end", iid=f"{m['model']}{SEP}{c['model']}", text=c["model"],
                                 tags=("sub", *(("err",) if c["errors"] and c["errors"] == c["requests"] else ())),
                                 values=values(c))
        if keep and self.tree.exists(keep):
            self.tree.selection_set(keep)
        self._render_breakdown()
        if rows:
            self.usage_empty.grid_forget()
        else:
            on = self.profile["observability"].get("jsonl_traces", True)
            self.usage_empty.configure(text="No model was used in this period." + (
                "" if on else " Usage traces are off: turn on 'Write usage traces' in Settings."))
            self.usage_empty.grid(row=1, column=0, sticky="w", pady=(8, 0))
        if self.usage_notes:
            self.usage_gaps.configure(text="Not counted: " + "; ".join(self.usage_notes) + ".")
            self.usage_gaps.grid(row=4, column=0, columnspan=2, sticky="we", pady=(4, 0))
        else:
            self.usage_gaps.grid_forget()
        self._draw_chart()

    def _selected_usage_row(self) -> dict | None:
        """The usage figures behind the selected table row: a model, or one client under it."""
        sel = self.tree.selection() if hasattr(self, "tree") else ()
        if not sel or self.usage_data is None:
            return None
        name, _, client = sel[0].partition(SEP)
        model = next((m for m in self.usage_data["models"] if m["model"] == name), None)
        if model and client:
            return next((c for c in model["clients"] if c["model"] == client), None)
        return model

    def _render_breakdown(self) -> None:
        if self.usage_data is None or not hasattr(self, "breakdown"):
            return
        m = self._selected_usage_row()
        sel = self.tree.selection()
        title = sel[0].replace(SEP, "  ·  ") if m and sel else "All models"
        self.breakdown.configure(text=usage.breakdown_text(m or self.usage_data["totals"], title))

    def _draw_chart(self) -> None:
        if self.usage_data is None or not hasattr(self, "canvas"):
            return
        t, c = self.t, self.canvas
        c.delete("all")
        sel = self.tree.selection()
        days = self.usage_data["days"]
        # A row is charted in its own unit (tokens, audio minutes, images); all models together in requests.
        if sel:
            model = self._selected_usage_row()
            kind = usage.measure(model) if model else "tokens"
            title, self.chart_unit, field = usage.MEASURES[kind]
            values = model[field] if model else [0] * len(days)
            self.chart_title.configure(text=f"{title}  ·  {sel[0].replace(SEP, '  ·  ')}")
        else:
            title, self.chart_unit, field = usage.MEASURES["requests"]
            values = self.usage_data["totals"][field]
            self.chart_title.configure(text=f"{title}  ·  all models (select a row for its tokens, audio or images)")
        w, h = max(c.winfo_width(), 200), max(c.winfo_height(), 100)
        left, right, top, bottom = 48, 8, 8, 22
        top_val = max(values) if any(values) else 1
        plot_h, plot_w = h - top - bottom, w - left - right
        for frac in (0, 0.5, 1):  # recessive hairline grid with compact labels
            y = top + plot_h * (1 - frac)
            c.create_line(left, y, w - right, y, fill=t["grid"] if frac else t["border"])
            label = f"{top_val * frac:.1f}" if top_val < 10 and top_val * frac != int(top_val * frac) else compact(top_val * frac)
            c.create_text(left - 8, y, text=label, anchor="e", fill=t["muted"], font=(FONT, 8))
        n = len(values)
        slot = plot_w / n
        bar_w = max(2.0, min(48.0, slot - 2))  # 2px surface gap between bars
        step = 1 if n <= 10 else 5
        self.bars = []
        for i, (d, v) in enumerate(zip(days, values)):
            x0 = left + i * slot + (slot - bar_w) / 2
            x1 = x0 + bar_w
            base = top + plot_h
            if v:
                y0 = top + plot_h * (1 - v / top_val)
                r = min(4, bar_w / 2, (base - y0))
                self._round_top_rect(x0, min(y0, base - 1), x1, base, r, t["accent"])
            self.bars.append((left + i * slot, left + (i + 1) * slot, d, v))
            if i % step == 0 or i == n - 1:
                label = "Today" if d == date.today().isoformat() else datetime.fromisoformat(d).strftime("%b %d").replace(" 0", " ")
                c.create_text((x0 + x1) / 2, h - 8, text=label, fill=t["muted"], font=(FONT, 8))

    def _round_top_rect(self, x0, y0, x1, y1, r, fill) -> None:
        """Bar with 4px rounded top corners, square at the baseline."""
        c = self.canvas
        c.create_rectangle(x0, y0 + r, x1, y1, fill=fill, width=0)
        if r < 1:
            return
        c.create_rectangle(x0 + r, y0, x1 - r, y0 + r, fill=fill, width=0)
        c.create_oval(x0, y0, x0 + 2 * r, y0 + 2 * r, fill=fill, width=0)
        c.create_oval(x1 - 2 * r, y0, x1, y0 + 2 * r, fill=fill, width=0)

    def _chart_hover(self, e) -> None:
        c, t = self.canvas, self.t
        c.delete("tip")
        bar = next((b for b in self.bars if b[0] <= e.x < b[1]), None)
        if not bar:
            return
        x0, x1, d, v = bar
        c.create_rectangle(x0, 8, x1, c.winfo_height() - 22, fill=t["hover"], width=0, tags="tip")
        c.tag_lower("tip")
        amount = f"{v:,.1f}" if isinstance(v, float) and v != int(v) else f"{int(v):,}"
        text = f"{datetime.fromisoformat(d).strftime('%a %b %d')}: {amount} {getattr(self, 'chart_unit', 'tokens')}"
        tx = min(max(e.x + 12, 4), c.winfo_width() - 230)
        item = c.create_text(tx + 8, 16, text=text, anchor="nw", fill=t["ink"], font=(FONT, 9), tags="tip")
        bx0, by0, bx1, by1 = c.bbox(item)
        bg = c.create_rectangle(bx0 - 8, by0 - 5, bx1 + 8, by1 + 5, fill=t["card"], outline=t["border"], tags="tip")
        c.tag_lower(bg, item)

    # ---------- Settings tab ----------
    def _build_settings(self, tab: ttk.Frame) -> None:
        self.tabs.add(tab, text="Settings")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)
        outer = tk.Frame(tab, bg=self.t["border"], padx=1, pady=1)
        outer.grid(row=0, column=0, sticky="nsew")
        holder, form = self._scroll_area(tab, outer, self.t["card"], style="Card.TFrame", padding=(18, 14))
        holder.pack(fill="both", expand=True)
        form.columnconfigure(1, weight=1)
        self.form = form

        groups = [("Models", "models"), ("Tracing and services", ("observability", "services")),
                  ("Voice typing", "dictation"), ("Refine selected text", "refine"), ("Ollama runtime", "ollama_env")]
        self.setting_vars: dict[str, tk.Variable | TextVar] = {}
        self.model_boxes: list[ttk.Combobox] = []
        self.changed_marks: dict[str, ttk.Label] = {}
        self.default_buttons: dict[str, tuple[ttk.Button, object]] = {}  # "text" settings: Restore default
        self.advanced_parts: list[dict] = []
        row = 0
        for title, sections in groups:
            ttk.Label(form, text=title, style="Card.Title.TLabel").grid(row=row, column=0, columnspan=3, sticky="w", pady=(8 if row else 0, 4))
            row += 1
            if title == "Ollama runtime":
                ttk.Label(form, text="Applying any of these restarts Ollama, which interrupts requests in progress.",
                          style="Card.Muted.TLabel").grid(row=row, column=0, columnspan=3, sticky="w", pady=(0, 6))
                row += 1
            in_group = [s for s in cfg.SETTINGS if s.section in (sections if isinstance(sections, tuple) else (sections,))]
            for s in in_group:
                if not s.advanced:
                    row = self._add_setting(form, s, row)
            if any(s.advanced for s in in_group):
                row = self._build_advanced(form, row, [s for s in in_group if s.advanced])
            if title == "Models":
                self.cloud_label = ttk.Label(form, text="", style="Card.Muted.TLabel", wraplength=640, justify="left")
                self.cloud_label.grid(row=row, column=0, columnspan=3, sticky="w", pady=(4, 0))
                self.settings_warning = ttk.Label(form, text="", style="Warn.TLabel", wraplength=640, justify="left")
                self.settings_warning.grid(row=row + 1, column=0, columnspan=3, sticky="w")
                row += 2

        bar = ttk.Frame(tab, padding=(0, 12, 0, 0))
        bar.grid(row=1, column=0, sticky="we")
        bar.columnconfigure(0, weight=1)
        self.pending_label = ttk.Label(bar, text="", style="HeadSub.TLabel", wraplength=520, justify="left")
        self.pending_label.grid(row=0, column=0, sticky="w")
        ttk.Button(bar, text="Open profile file", command=lambda: self.open_path(prof.machine_file(self.profile["name"]))).grid(row=0, column=1, padx=4)
        self.revert_btn = ttk.Button(bar, text="Revert", command=self._load_settings)
        self.revert_btn.grid(row=0, column=2, padx=4)
        self.apply_btn = ttk.Button(bar, text="Apply", style="Accent.TButton", command=self._apply_settings)
        self.apply_btn.grid(row=0, column=3)
        self.apply_log = ttk.Label(bar, text="", style="HeadSub.TLabel", wraplength=820, justify="left")
        self.apply_log.grid(row=1, column=0, columnspan=4, sticky="w", pady=(6, 0))
        self._load_settings()

    def _add_setting(self, parent, s, row: int) -> int:
        """One setting from grid row `row`: label, control and "changed" mark, then its help. Returns the next free row.
        A "text" setting puts its help under the label and its box across the whole width below."""
        sid = cfg.setting_id(s)
        ttk.Label(parent, text=s.label, style="Card.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 24), pady=(6, 0))
        mark = ttk.Label(parent, text="", style="Warn.TLabel")
        mark.grid(row=row, column=2, sticky="e", pady=(6, 0))
        self.changed_marks[sid] = mark
        if s.kind == "text":
            ttk.Label(parent, text=s.help, style="Card.Muted.TLabel", wraplength=640, justify="left").grid(
                row=row + 1, column=0, columnspan=3, sticky="w", pady=(0, 4))
            var, box = self._text_box(parent, s)
            box.grid(row=row + 2, column=0, columnspan=3, sticky="we", pady=(2, 6))
            self.setting_vars[sid] = var
            return row + 3
        if s.kind == "bool":
            var: tk.Variable = tk.BooleanVar()
            widget = ttk.Checkbutton(parent, variable=var, text="On", command=self._settings_dirty)
        elif s.kind == "search":
            # Too many values for a drop-down (100 languages): a button that opens the search picker.
            var = tk.StringVar()
            widget = ttk.Button(parent, width=30)
            widget.configure(command=lambda s=s, v=var, b=widget: self._pick_setting(s, v, b))
            var.trace_add("write", lambda *_a, s=s, v=var, b=widget: b.configure(
                text=f"{s.labels.get(v.get(), v.get())}  ▾"))
        else:
            var = tk.StringVar()
            widget = ttk.Combobox(parent, textvariable=var, values=s.choices, state="readonly", width=30)
            widget.bind("<<ComboboxSelected>>", lambda _e: self._settings_dirty())
            if s.kind == "model":
                self.model_boxes.append(widget)
        widget.grid(row=row, column=1, sticky="w", pady=(6, 0))
        self.setting_vars[sid] = var
        ttk.Label(parent, text=s.help, style="Card.Muted.TLabel", wraplength=560, justify="left").grid(
            row=row + 1, column=0, columnspan=2, sticky="w", pady=(0, 4))
        return row + 2

    def _text_box(self, parent, s) -> tuple["TextVar", ttk.Frame]:
        """A setting of several lines (voice typing's cleanup prompt): a text box, and Restore default under it."""
        t = self.t
        frame = ttk.Frame(parent, style="Card.TFrame")
        frame.columnconfigure(0, weight=1)
        box = tk.Text(frame, height=12, width=72, wrap="word", undo=True, maxundo=-1, font=(FONT, 10),
                      bg=t["page"], fg=t["ink"], insertbackground=t["ink"], selectbackground=t["select"],
                      selectforeground=t["ink"], inactiveselectbackground=t["select"], relief="flat", borderwidth=0,
                      padx=8, pady=6, highlightthickness=2, highlightbackground=t["border"], highlightcolor=t["accent"])
        box.grid(row=0, column=0, sticky="we")
        # After Tk's own Text bindings: stop the wheel from also scrolling the tab while the box scrolls its text.
        box.bindtags((str(box), "Text", "SettingText", *box.bindtags()[2:]))
        box.bind("<<Modified>>", lambda _e: self._text_edited(box))
        box.bind("<Tab>", lambda _e: self._focus_step(box, 1))      # Tk would type a tab character; move on instead
        box.bind("<Shift-Tab>", lambda _e: self._focus_step(box, -1))
        var = TextVar(box)
        reset = ttk.Button(frame, text="Restore default",
                           command=lambda: (var.replace(s.default), self._settings_dirty(), box.focus_set()))
        reset.grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.default_buttons[cfg.setting_id(s)] = (reset, s)
        return var, frame

    def _text_edited(self, box: tk.Text) -> None:
        """<<Modified>> fires once per change of the box's modified flag: clear it so the next keystroke fires again."""
        if box.edit_modified():
            box.edit_modified(False)
            self._settings_dirty()

    @staticmethod
    def _focus_step(widget, step: int) -> str:
        target = widget.tk_focusNext() if step > 0 else widget.tk_focusPrev()
        if target is not None:
            target.focus_set()
        return "break"

    def _build_advanced(self, form, row: int, items: list) -> int:
        """A group's rarely changed settings behind Show advanced, closed until opened. A note beside the button says
        when one of them is not the built-in value, so a closed part never hides a change from you."""
        head = ttk.Frame(form, style="Card.TFrame")
        head.grid(row=row, column=0, columnspan=3, sticky="w", pady=(10, 2))
        part = {"items": items, "open": False, "button": ttk.Button(head),
                "note": ttk.Label(head, text="", style="Card.Muted.TLabel")}
        part["button"].configure(command=lambda: self._toggle_advanced(part))
        part["button"].pack(side="left")
        part["note"].pack(side="left", padx=(10, 0))
        before = set(form.grid_slaves())
        row += 1
        for s in items:
            row = self._add_setting(form, s, row)
        part["widgets"] = [w for w in form.grid_slaves() if w not in before]
        self.advanced_parts.append(part)
        self._toggle_advanced(part, False)
        return row

    def _toggle_advanced(self, part: dict, show: bool | None = None) -> None:
        part["open"] = not part["open"] if show is None else show
        for w in part["widgets"]:
            if part["open"]:
                w.grid()
            else:
                w.grid_remove()
        part["button"].configure(text=("Hide advanced  ▴" if part["open"] else "Show advanced  ▾"))

    def _note_advanced(self, part: dict) -> None:
        values = cfg.current_values(self.profile)
        own = [s.label.lower() for s in part["items"]
               if s.kind == "text" and values[cfg.setting_id(s)] != cfg.tidy_text(s.default)]
        part["note"].configure(text=f"Your own {' and '.join(own)} is in use." if own else "")

    def _pick_setting(self, s, var: tk.StringVar, button: ttk.Button) -> None:
        """Open the type-to-search picker under a "search" setting's button (voice typing's 100 languages)."""
        from stacklib.dictation import models
        from stacklib.dictation.picker import Picker

        t = self.t
        palette = {"bg": t["card"], "field": t["page"], "fg": t["ink"], "muted": t["muted"], "border": t["border"],
                   "select_bg": t["accent"], "select_fg": t["accent_ink"], "accent": t["accent"]}
        anchor = (button.winfo_rootx(), button.winfo_rooty(), button.winfo_width(), button.winfo_height())

        def choose(code: str) -> None:
            var.set(code)
            self._settings_dirty()
            button.focus_set()

        Picker(self.window, [(c, s.labels.get(c, c)) for c in s.choices], var.get(), choose, models.search,
               title=s.label, anchor=anchor, palette=palette)

    def _load_settings(self) -> None:
        self.profile = prof.resolve_profile(self.profile["name"])
        usage_log.configure(self.profile)
        values = cfg.current_values(self.profile)
        models = cfg.installed_models(self.profile)
        for box in self.model_boxes:
            box.configure(values=models)
        for sid, var in self.setting_vars.items():
            var.set(values[sid])
            if sid.startswith("models.") and isinstance(var, tk.StringVar) and values[sid] and values[sid] not in models:
                for box in self.model_boxes:  # keep the configured model selectable even when it is not pulled
                    box.configure(values=sorted({*box.cget("values"), values[sid]}))
        self.cloud_label.configure(text=(
            "External models: off. Every tier runs on local models, whatever .env holds; external models wait for "
            "the privacy gate and external.enabled in policy/privacy.yaml (docs/plans/)."))
        for part in self.advanced_parts:
            self._note_advanced(part)
        self._settings_dirty()

    def _edits(self) -> dict[str, object]:
        return {sid: var.get() for sid, var in self.setting_vars.items()}

    def _settings_dirty(self) -> None:
        edits = self._edits()
        todo = cfg.changed(self.profile, edits)
        ids = {cfg.setting_id(s) for s in todo}
        for sid, mark in self.changed_marks.items():
            mark.configure(text="changed" if sid in ids else "")
        warn = ""
        if edits["models.primary"] == edits["models.small"] and edits["models.primary_num_ctx"] != edits["models.small_num_ctx"]:
            warn = "Primary and small use the same model with different contexts: Ollama will reload it whenever the tier switches."
        if not edits["observability.jsonl_traces"]:
            warn = (warn + " " if warn else "") + "With usage traces off, the Usage tab and the retrospective get no new data."
        self.settings_warning.configure(text=warn)
        for sid, (button, s) in self.default_buttons.items():
            button.configure(state="normal" if cfg.tidy_text(edits[sid]) != cfg.tidy_text(s.default) else "disabled")
        if todo:
            effects = cfg.effect_texts(todo)
            self.pending_label.configure(text=f"{len(todo)} unsaved change{'s' if len(todo) > 1 else ''}. Apply will: " + "; ".join(effects) + ".")
        else:
            self.pending_label.configure(text=f"Saved in machines/{self.profile['name']}.yaml. Defaults come from machines/_defaults.yaml.")
        state = "normal" if todo and not self.busy and not self.pending else "disabled"
        self.apply_btn.configure(state=state)
        self.revert_btn.configure(state=state)

    def _apply_settings(self) -> None:
        edits = self._edits()
        todo = cfg.changed(self.profile, edits)
        if not todo:
            return
        if any(s.effect == "ollama" for s in todo) and not messagebox.askokcancel(
                "Restart Ollama?", "These changes restart Ollama. Requests in progress will fail and the next one reloads the model.",
                parent=self.window):
            return
        lines: list[str] = []

        def log(msg: str) -> None:
            print(f"[tray] settings: {msg}")
            lines.append(msg)
            self.ui_queue.put(lambda text="  ·  ".join(lines[-4:]): self.apply_log.configure(text=text))

        def run() -> None:
            try:
                new = cfg.apply(self.profile, edits, log=log)
                self.profile = new
                usage_log.configure(new)  # "Write usage traces" also switches the usage records
                usage_log.sync_switch(new)
                self.managed = [s for s in services.SERVICE_ORDER if s in services.commands(new)]
                log("Done.")
            except Exception as e:  # noqa: BLE001 - report every failure in the window
                log(f"Failed: {e}")
            finally:
                self.busy = ""
                self.clients_checked = 0.0  # a service turned on or off changes the Features card: check again now
                self.ui_queue.put(self._load_settings)
                self.refresh_soon()

        self.busy = "applying settings"
        self._settings_dirty()
        self._render_services()
        threading.Thread(target=run, daemon=True).start()

    def _drain_ui_queue(self) -> None:
        try:
            while True:
                fn = self.ui_queue.get_nowait()
                try:
                    fn()
                except Exception as e:  # noqa: BLE001 - one bad render must not stop the UI loop
                    print(f"[tray] ui update failed: {e}")
        except queue.Empty:
            pass
        if startup.take_show_request():  # Start menu entry, start.cmd or `stack.py tray` while this tray runs
            self.show_window(0)
        if not self.stop_event.is_set():
            self.root.after(100, self._drain_ui_queue)

    def run(self) -> None:
        threading.Thread(target=self._poll, daemon=True).start()
        self.icon.run_detached()
        self.root.after(100, self._drain_ui_queue)
        if "--show" in sys.argv:
            self.ui_queue.put(lambda: self.show_window(0))
        self.root.mainloop()


def main() -> int:
    print(f"[tray] {datetime.now().isoformat(timespec='seconds')} starting pid {os.getpid()}")
    if not startup.claim_single_instance():
        if "--show" in sys.argv:
            startup.request_show()
        print("[tray] another tray instance is running; exiting")
        return 0
    startup.take_show_request()  # drop a request left over from an earlier run
    app = TrayApp(autostart="--no-autostart" not in sys.argv)  # an error here reaches _report_startup_failure
    app.root.after(0, lambda: print(f"{READY} pid {os.getpid()}"))  # runs once the icon is up and the Tk loop turns
    app.run()
    print("[tray] exited")
    return 0


if __name__ == "__main__":
    sys.exit(main())
