#!/usr/bin/env python3
"""Agent Stack tray app: keeps the stack's services running in the background and shows their status.

It lives in the notification area (on Windows it starts among the hidden icons). Left-click or "Show status" opens a
window with four tabs:
  Overview  each module's health under the name of what it does (the program behind it on the line below), with
            Open / Hide / Show and Start or Stop, and a row per process for models that run in one of their own
            (Ollama's runners, the recordings server); the models loaded on the GPU; the features the installer
            offers, each with Install, Repair or Remove (run by the setup worker, stacklib/install.py and
            uninstall.py) and, under Local models, Download or Remove per model; and Storage: every model, program
            and data folder the stack keeps on disk, per drive
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
from stacklib import comfy_usage, features, gpu_models, install, modules, startup, storage, uninstall  # noqa: E402
from stacklib import usage, usage_log  # noqa: E402

POLL_SECONDS = 10
CLIENT_SECONDS = 60  # between feature checks (OpenClaw's config, the uv tool environments, the models Ollama has)
START_TIMEOUT = 180  # seconds a started service gets to answer its health check
RESOURCE_SECONDS = 5  # pause between process samples while the Resources tab is on screen
RESOURCES_TAB = 3
# Each row is named for what the module does, not for the program or model behind it; ROLES names the program.
LABELS = {
    "ollama": "Local models",
    "phoenix": "Trace viewer",
    "litellm": "Gateway",
    "orchestrator": "Agent tools",
    "open_webui": "Chat in the browser",
    "comfyui": "Image generation",
    "kokoro": "Read aloud",
    "dictation": "Voice typing",
}
ROLES = {
    "ollama": "Ollama: runs the chat, embedding and autocomplete models",
    "phoenix": "Phoenix: shows the steps of each request",
    "litellm": "LiteLLM: one address for every model, with the privacy rules",
    "orchestrator": "orchestrator MCP: agents hand work to the departments",
    "open_webui": "Open WebUI: chat with the department models",
    "comfyui": "ComfyUI: pictures for the chat's image button",
    "kokoro": "Kokoro: text to speech",
    "dictation": "Whisper: speech to text in any app",
}
# The Services card's order: what everything else needs first, then the apps on top of it.
ROW_ORDER = ["ollama", "litellm", "orchestrator", "open_webui", "phoenix", "comfyui", "dictation", "kokoro"]
OLLAMA_SLOTS = 4   # rows for Ollama's runners, one per loaded model (OLLAMA_MAX_LOADED_MODELS is 1 or 2 here)
# Feature states where setup can put back what is missing (a model, the files, Claude Desktop's entry): Repair.
REPAIR_STATES = {"Models missing", "Model missing", "Files missing", "Not in Claude Desktop"}
FONT = "Segoe UI" if IS_WINDOWS else "TkDefaultFont"
# Spacing tokens (px), so every card uses the same few gaps.
GAP_XS, GAP_S, GAP_M, GAP_L, GAP_XL = 4, 8, 12, 16, 24
BTN_A, BTN_B = 13, 10   # widths (characters) of the two action columns: Open / Hide / Show, and Start / Stop
# Storage bar: categorical slots 1-3 of the dataviz palette (blue, orange, aqua), stepped per theme. Validated against
# the card colours: they pass the colour-vision checks in both themes; light aqua is below 3:1 on the card, so the
# legend and the table beside the bar carry every figure.
STORAGE_COLORS = {"light": ("#2a78d6", "#eb6834", "#1baf7a"), "dark": ("#3987e5", "#d95926", "#199e70")}
STORAGE_BAR_PX = 8
STORAGE_SECONDS = 600   # measure again by itself at most this often; Refresh measures at once
SETTING_CONTROL_W = "2.7i"   # Settings cards' control column, wider than its widest control (scales with DPI)
SETTING_GROUPS = [
    ("Models", "models", "Which local models answer the gateway's aliases, and how much context each one gets."),
    ("Services and tracing", ("observability", "services"),
     "What the stack runs, and what it records about each request."),
    ("Voice typing", "dictation", "The mic button and the hotkey that type what you say into any app."),
    ("Refine selected text", "refine", "The pencil button and the hotkeys that rewrite the text you selected."),
    ("Read aloud", "read_aloud", "The speaker button and the hotkey that read the text you selected aloud."),
    ("Ollama runtime", "ollama_env", "Applying any of these restarts Ollama, which interrupts requests in progress."),
]

# Window palette (light / dark): neutral surfaces, one blue accent for data, status colours only for state.
# Every colour used for text (ink2, muted, accent, good, warn, bad) is at least 4.5:1 on page and card, and accent_ink
# at least 4.5:1 on accent (WCAG AA); check changes with .claude/skills/ux-rules/scripts/contrast.py. Buttons get a
# fill of their own (control, a step off the card) and an outline, so they read as buttons in a grayscale screenshot;
# ink is 13:1 or more on control and control_hover, danger (Remove, Delete) 4.5:1 or more on card and hover.
THEMES = {
    "light": {
        "page": "#f3f3f1", "card": "#fcfcfb", "ink": "#0b0b0b", "ink2": "#52514e", "muted": "#6b6a65",
        "grid": "#e1e0d9", "border": "#dcdbd4", "accent": "#2368c0", "accent_ink": "#ffffff", "hover": "#ebeae5",
        "good": "#087a08", "warn": "#8a5f00", "bad": "#c03535", "select": "#dbe8f8",
        "control": "#f3f3f1", "control_hover": "#e7e6e0", "control_border": "#c9c8c0", "danger": "#c03535",
    },
    "dark": {
        "page": "#111110", "card": "#1a1a19", "ink": "#f0efec", "ink2": "#c3c2b7", "muted": "#898781",
        "grid": "#2c2c2a", "border": "#33332f", "accent": "#3987e5", "accent_ink": "#0b0b0b", "hover": "#252523",
        "good": "#0ca30c", "warn": "#fab219", "bad": "#e05252", "select": "#1f3a5c",
        "control": "#262624", "control_hover": "#30302d", "control_border": "#4a4945", "danger": "#ec6a6a",
    },
}
RANGES = [("Today", 1), ("7 days", 7), ("30 days", 30)]
SEP = "\x1f"  # joins a model and a client in a Usage table row id


def dark_title_bar(window) -> None:
    """A dark title bar on Windows when the system uses the dark theme (DWMWA_USE_IMMERSIVE_DARK_MODE)."""
    if not (IS_WINDOWS and system_theme() == "dark"):
        return
    try:
        import ctypes

        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(ctypes.c_int(1)), 4)
    except (OSError, AttributeError):
        pass


def ollama_log() -> Path:
    """The Ollama app's server log, for Show log on its row."""
    if IS_WINDOWS:
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Ollama" / "server.log"
    return Path.home() / ".ollama" / "logs" / "server.log"


MODEL_ROLES = {"fim": "autocomplete", "embed": "embeddings", "small": "chat", "primary": "chat", "reviewer": "code review"}


def model_role(m) -> str:
    """What a catalog model is for, in a word or two ("" for a model the catalog does not know)."""
    return MODEL_ROLES.get(getattr(m, "role", ""), "")


def model_line(m) -> str:
    """The line under a model's name on the Features card: what the stack uses it for, or what it is."""
    role = model_role(m)
    kind = f"{role} model" if role else "model"
    if m.downloaded:
        return f"in use: {m.use}" if m.use else f"{kind}, not used by the stack"
    return f"{kind}, not downloaded" + (f"; Settings names it for {m.use}" if m.use else "")


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
        self.gpu_rows: list[dict] = []     # every model on the GPU: Ollama's, Whisper, ComfyUI's
        self.dictation_health: dict | None = None
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
        self.read_button: bool | None = None       # and the read aloud (speaker) button
        self.ollama_tree: dict = {"pid": None, "runners": []}   # Ollama's server and one runner per loaded model
        self.unloading: set[str] = set()           # models an Unload click is taking out of Ollama
        self.model_rows: list = []                 # Local models: every catalog model and any other Ollama has
        self.setup_state: dict = {}                # the setup worker's state (stacklib/install.py read_state)
        self.setup_seen: str | None = None         # the last finished run the tray handled (None until the first read)
        self.setup_watch = False                   # show the setup line: a run was seen while it worked
        self.setup_job: str | None = None          # the 1 s redraw while the setup worker runs
        self.setup_lock = threading.Lock()         # _check_setup runs on the poll thread and on refresh_soon's
        self.setup_read_at = 0.0                   # monotonic time of the setup state kept
        self.feature_starting: dict[str, str] = {}  # feature -> "Installing" / "Removing" while its worker starts
        self.storage: storage.Scan | None = None   # the Storage card's last measurement
        self.storage_busy = False
        self.storage_error = ""
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
        self._check_setup()
        self._check_dictation()
        self._check_processes()
        self._collect_usage()
        self._check_gpu_models()
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
            self.dictation_button = self.refine_button = self.read_button = None
            self.dictation_health = None
            return
        from stacklib.dictation import control

        try:
            health = control.call(int(self.profile["ports"]["dictation"]), "health", 1.5)
            self.dictation_health = health if isinstance(health, dict) else None
            self.dictation_button = bool(health.get("button", True))
            refine, read = health.get("refine"), health.get("read_aloud")
            self.refine_button = bool(refine.get("button", True)) if isinstance(refine, dict) else None
            on = isinstance(read, dict) and read.get("enabled", True)   # off: no speaker button to show or hide
            self.read_button = bool(read.get("button", True)) if on else None
        except (OSError, ValueError, AttributeError):
            self.dictation_button = self.refine_button = self.read_button = None
            self.dictation_health = None

    def _check_processes(self) -> None:
        """Pids for the Services card: Ollama's server and one runner per loaded model."""
        try:
            up = self.rows.get("ollama", {}).get("healthy")
            self.ollama_tree = modules.ollama_tree(self.loaded) if up else {"pid": None, "runners": []}
        except Exception as e:  # noqa: BLE001 - a process that vanished mid-scan must not stop the poller
            print(f"[tray] process check failed: {e}")

    def _check_setup(self) -> None:
        """The setup worker's state, whoever started it (Install or Remove here, or the installer window). Its steps
        show under the features while it runs; when a run ends, the tray reads the profile again, starts what it
        turned on, and checks the features and storage at once."""
        read_at, state = time.monotonic(), install.read_state()
        with self.setup_lock:
            if not self._set_setup_state(state, read_at):
                return   # a newer read is already in
            status = state.get("status")
            if status == "running":
                self.setup_watch = True
                self.setup_seen = self.setup_seen or "running"
                return
            key = f"{state.get('pid')}:{state.get('started')}:{status}"
            first = self.setup_seen is None
            if key == self.setup_seen:
                return
            self.setup_seen = key
        if not first and status:
            self._setup_finished(state)

    def _set_setup_state(self, state: dict, read_at: float) -> bool:
        """Keep the newest reading of the setup worker's state file (several threads read it); False when an older
        reading arrives after a newer one."""
        if read_at < self.setup_read_at:
            return False
        self.setup_read_at, self.setup_state = read_at, state
        return True

    def _setup_finished(self, state: dict) -> None:
        old_profile, old = self.profile, set(self.managed)
        self.profile = prof.resolve_profile(self.profile["name"])
        usage_log.configure(self.profile)
        self.managed = [s for s in services.SERVICE_ORDER if s in services.commands(self.profile)]
        self.feature_est = features.estimates(self.profile, self.hardware, self.loaded)
        self.clients_checked = 0.0   # the features changed: check them in this pass
        new = [s for s in self.managed if s not in old and not self.rows.get(s, {}).get("healthy")]
        # The gateway's environment names the image model for the reply label (services.gateway_label_env): an image
        # feature set up here (not through Settings, which restarts it itself) needs the gateway restarted.
        relabel = "images" in (state.get("targets") or []) and not (state.get("remove") or []) \
            and self.rows.get("litellm", {}).get("healthy") and "litellm" in self.managed
        print(f"[tray] setup finished ({state.get('status')}); starting {', '.join(new) or 'nothing new'}"
              + ("; restarting the gateway for the image label" if relabel else ""))

        def ui() -> None:
            if new:
                self._act("start", new)
            if relabel:
                self.restart_service("litellm")
            if self._window_built():
                if not cfg.changed(old_profile, self._edits()):
                    self._load_settings()   # Settings shows the switches the run changed (unless it holds edits)
                self.scan_storage(force=True)
        self.ui_queue.put(ui)

    def _check_gpu_models(self) -> None:
        """The GPU card's rows: Ollama's models plus voice typing's Whisper and ComfyUI's models when they hold the card."""
        stats, label = None, ""
        if self.rows.get("comfyui", {}).get("healthy"):
            stats = gpu_models.comfy_stats(int(self.profile["ports"]["comfyui"]))
            workflow = media.media(self.profile).get("image_workflow") or "z_image_turbo"
            label = media.WORKFLOW_LABELS.get(workflow, workflow)
        self.gpu_rows = gpu_models.rows(self.loaded, self.dictation_health, stats, label)

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
        """OpenClaw's config: whether the gateway is its only model endpoint (its Features row and Use gateway)."""
        try:
            return {"openclaw": clients.openclaw(self.profile["ports"]["litellm"])}
        except Exception as e:  # noqa: BLE001 - a bad config file must not stop the poller
            return {"openclaw": clients.ClientStatus("warn", "Not checked", str(e) or type(e).__name__)}

    def _check_features(self) -> None:
        """What is installed, on and linked (stacklib/features.py), and what each feature takes with the models that
        are loaded now. Reuses the OpenClaw check _check_clients just made."""
        try:
            self.feature_status = features.statuses(self.profile, openclaw=self.client_status.get("openclaw"))
            self.feature_est = features.estimates(self.profile, self.hardware, self.loaded)
            self.model_rows = uninstall.model_rows(self.profile)
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
    def _setup_owns(self, svc: str) -> bool:
        """The setup worker is installing or removing the feature this service belongs to: hands off until it ends."""
        st = self.setup_state
        return st.get("status") == "running" and features.SERVICE_FEATURE.get(svc) in (st.get("targets") or [])

    def restart_service(self, svc: str) -> None:
        """Stop and start one service, with its row showing Starting while it comes back."""
        if svc in self.pending:
            return
        entry = ("start", time.monotonic())
        self.pending[svc] = entry
        self._render_services()
        self._tick_soon()

        def run() -> None:
            problem = None
            try:
                with self.service_locks[svc]:
                    services.stop(self.profile, [svc])
                    reasons = services.start(self.profile, [svc])
                if svc in reasons:
                    problem = (f"Not restarted: {reasons[svc]}.", services.log_file(self.profile, svc))
                elif not services.wait_healthy(self.profile, [svc], timeout=START_TIMEOUT)[svc]:
                    problem = ("No answer from its health check after the restart.", services.log_file(self.profile, svc))
            except Exception as e:  # noqa: BLE001 - shown on the row
                traceback.print_exc()
                problem = (f"Could not restart: {e}", LOG_FILE)
            checked = time.monotonic()
            row = services.probe(self.profile, svc)
            self.ui_queue.put(lambda: self._action_done(svc, entry, row, checked, problem))

        threading.Thread(target=run, daemon=True, name=f"restart-{svc}").start()

    def _running(self, svc: str) -> bool:
        """Running, starting, or being started: what Stop applies to."""
        pending = self.pending.get(svc)
        return pending[0] == "start" if pending else self.rows.get(svc, {}).get("state", "stopped") != "stopped"

    def start_all(self, *_):
        self._on_ui(lambda: self._act("start", [s for s in self.managed if not self._running(s) and s not in self.pending
                                                and not self._setup_owns(s)]))

    def stop_all(self, *_):
        self._on_ui(lambda: self._act("stop", [s for s in self.managed if self._running(s) and not self._setup_owns(s)]))

    def toggle(self, svc: str) -> None:
        if svc == "ollama":   # the Ollama app's server: Start brings the app back, nothing here stops it
            self.start_ollama()
            return
        if self._setup_owns(svc):
            return
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
    def _kokoro_in_app(self, svc: str) -> bool:
        """The Kokoro row shows read aloud (Kokoro inside voice typing) while the standalone Kokoro service is off."""
        return svc == "kokoro" and svc not in self.managed

    def _status_text(self, svc: str):
        def text(_item) -> str:
            if self._kokoro_in_app(svc):
                state = features.read_aloud_row(self.profile, self.dictation_health,
                                                self.feature_status.get("read_aloud"))[1]
                return f"{LABELS[svc]} (read aloud): {state.lower()}"
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
            pystray.MenuItem("Open installer...", self.open_installer),
            pystray.Menu.SEPARATOR,
            *[pystray.MenuItem(self._status_text(s), None, enabled=False) for s in self._service_order()],
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
            pystray.MenuItem("Read aloud button (speaker)", lambda *_: self.set_read_button(not self.read_button),
                             checked=lambda _item: bool(self.read_button),
                             visible=lambda _item: self.read_button is not None),
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

    def set_read_button(self, visible: bool) -> None:
        """The same for the read aloud (speaker) button (read_aloud.button)."""
        self.read_button = visible
        self._overlay_button("show_read" if visible else "hide_read", "read aloud")

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
                    note = "Opening the installer; this card follows its setup while it runs."
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
        self.scan_storage()

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
        s.configure("Card.Name.TLabel", background=t["card"], foreground=t["ink"], font=(FONT, 10, "bold"))
        s.configure("Head.TLabel", background=t["page"], foreground=t["ink"], font=(FONT, 16, "bold"))
        s.configure("HeadSub.TLabel", background=t["page"], foreground=t["ink2"])
        s.configure("Warn.TLabel", background=t["card"], foreground=t["warn"])
        s.configure("Bad.TLabel", background=t["card"], foreground=t["bad"])
        # Keyboard focus: clam's dotted ring inside, plus a 2 px solid ring (clam draws a border only for a solid or
        # raised relief). Rings are accent on surfaces and ink or accent-ink on accent fills, 3:1 or more either way.
        s.configure("TButton", background=t["control"], foreground=t["ink"], padding=(10, 4), relief="solid", borderwidth=1,
                    bordercolor=t["control_border"], lightcolor=t["control"], darkcolor=t["control"])
        s.map("TButton", background=[("disabled", t["card"]), ("active", t["control_hover"])],
              lightcolor=[("disabled", t["card"]), ("active", t["control_hover"])],
              darkcolor=[("disabled", t["card"]), ("active", t["control_hover"])],
              foreground=[("disabled", t["muted"])], bordercolor=[("focus", t["accent"]), ("disabled", t["border"])])
        s.configure("Accent.TButton", background=t["accent"], foreground=t["accent_ink"], bordercolor=t["accent"],
                    lightcolor=t["accent"], darkcolor=t["accent"], focuscolor=t["accent_ink"])
        s.map("Accent.TButton", background=[("disabled", t["border"]), ("active", t["accent"])],
              lightcolor=[("disabled", t["border"]), ("active", t["accent"])],
              darkcolor=[("disabled", t["border"]), ("active", t["accent"])], bordercolor=[("focus", t["ink"])])
        # A destructive action (Remove, Delete model): outlined in the danger colour, never filled like the primary one.
        s.configure("Danger.TButton", background=t["card"], foreground=t["danger"], bordercolor=t["danger"],
                    lightcolor=t["card"], darkcolor=t["card"])
        s.map("Danger.TButton", background=[("active", t["hover"])], lightcolor=[("active", t["hover"])],
              darkcolor=[("active", t["hover"])], foreground=[("disabled", t["muted"])], bordercolor=[("focus", t["ink"])])
        s.configure("Horizontal.TProgressbar", background=t["accent"], troughcolor=t["grid"], bordercolor=t["card"],
                    lightcolor=t["accent"], darkcolor=t["accent"])
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
        inner = ttk.Frame(outer, style="Card.TFrame", padding=GAP_L)
        inner.pack(fill="both", expand=True)
        if title:
            ttk.Label(inner, text=title, style="Card.Title.TLabel").grid(row=0, column=0, columnspan=10, sticky="w", pady=(0, GAP_M))
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
        w.geometry(f"960x{min(900, w.winfo_screenheight() - 80)}")  # Overview scrolls: services, GPU, features, storage
        w.minsize(780, 560)
        w.protocol("WM_DELETE_WINDOW", w.withdraw)  # closing hides it; the tray keeps running
        dark_title_bar(w)
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
        self._build_overview(ttk.Frame(self.tabs, padding=(0, GAP_M, 0, 0)))
        self._build_usage(ttk.Frame(self.tabs, padding=(0, GAP_M, 0, 0)))
        self._build_settings(ttk.Frame(self.tabs, padding=(0, GAP_M, 0, 0)))
        self._build_resources(ttk.Frame(self.tabs, padding=(0, GAP_M, 0, 0)))

    # ---------- Overview tab ----------
    def _build_overview(self, tab: ttk.Frame) -> None:
        self.tabs.add(tab, text="Overview")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)
        # The cards scroll when the window is shorter than they are; the action bar below stays in view.
        holder, body = self._scroll_area(tab, tab, self.t["page"])
        holder.grid(row=0, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        self._build_services(body)
        self._build_gpu(body)
        self._build_features(body)
        self._build_storage(body)

        bar = ttk.Frame(tab, padding=(0, GAP_M, 0, 0))
        bar.grid(row=1, column=0, sticky="we")
        ttk.Button(bar, text="Open chat", style="Accent.TButton", command=lambda: self.open_url("open_webui")).pack(side="left")
        self.start_btn = ttk.Button(bar, text="Start all", command=self.start_all)
        self.start_btn.pack(side="left", padx=(GAP_S, GAP_XS))
        self.stop_btn = ttk.Button(bar, text="Stop all", command=self.stop_all)
        self.stop_btn.pack(side="left")
        ttk.Button(bar, text="Logs", command=self.open_logs).pack(side="left", padx=GAP_XS)
        self.startup_var = tk.BooleanVar(value=startup.is_installed())
        ttk.Checkbutton(bar, text="Start at login", style="Page.TCheckbutton", variable=self.startup_var,
                        command=self._toggle_startup).pack(side="right")

    def _service_order(self) -> list[str]:
        """The Services card's rows: ROW_ORDER, then any service it does not name yet."""
        known = ["ollama", *services.SERVICE_ORDER]
        return [s for s in ROW_ORDER if s in known] + [s for s in known if s not in ROW_ORDER]

    def _role(self, svc: str) -> str:
        """The line under a module's name: the program behind it and its port."""
        if self._kokoro_in_app(svc):   # read aloud runs Kokoro inside voice typing: no port of its own
            pid = self.rows.get("dictation", {}).get("pid")
            return "Kokoro: text to speech, inside voice typing" + (f" (pid {pid})" if pid else "")
        return f"{ROLES[svc]}  ·  port {self.profile['ports'][svc]}"

    def _line(self, parent, row: int, columns: int = 5) -> tk.Frame:
        """A hairline between two blocks of a card."""
        line = tk.Frame(parent, height=1, bg=self.t["grid"])
        line.grid(row=row, column=0, columnspan=columns, sticky="we", pady=GAP_S)
        return line

    @staticmethod
    def _action(parent, text: str, command, width: int = 0) -> ttk.Button:
        """One button in a row's first action column (Open, Hide or Show), stacked one per line."""
        btn = ttk.Button(parent, text=text, width=width or BTN_A, command=command)
        btn.pack(side="top", fill="x", pady=(0, GAP_XS))
        return btn

    def _build_services(self, body) -> None:
        """One block per module, named for what it does (the program behind it is on the line below): a dot, the
        state, then two action columns, Open / Hide / Show (one per line) and Start or Stop (blank where the stack
        does not start or stop it). Local models gets a row per model Ollama has loaded, since each runs in a runner
        process of its own. A failed start or stop adds a line with the reason."""
        t = self.t
        card = self._card(body, "Services", row=0, column=0)
        card.columnconfigure(1, weight=1)
        self.row_widgets: dict[str, dict] = {}
        self.reason_widgets: dict[str, tuple] = {}
        self.runner_slots: list[tuple] = []
        links = ui_links(self.profile)
        for n, svc in enumerate(self._service_order()):
            base = 10 * n + 1
            line = self._line(card, base) if n else None
            row = base + 1
            dot = tk.Label(card, text="●", font=(FONT, 12), bg=t["card"], fg=t["muted"])
            dot.grid(row=row, column=0, sticky="n", padx=(0, GAP_S))
            names = ttk.Frame(card, style="Card.TFrame")
            names.grid(row=row, column=1, sticky="nw")
            label, role = LABELS[svc], self._role(svc)
            ttk.Label(names, text=label, style="Card.Name.TLabel").pack(anchor="w")
            role_label = ttk.Label(names, text=role, style="Card.Muted.TLabel")
            role_label.pack(anchor="w")
            state = ttk.Label(card, text="", style="Card.Sub.TLabel", width=-20)
            state.grid(row=row, column=2, sticky="nw", padx=GAP_M)
            actions = ttk.Frame(card, style="Card.TFrame")
            actions.grid(row=row, column=3, sticky="ne", padx=(0, GAP_S))
            if svc in links:
                self._action(actions, "Open", lambda s=svc: self.open_url(s))
            if svc == "dictation":
                # Bring back (or hide) the floating mic and refine buttons without opening Settings.
                self.dictation_btn = self._action(actions, "Hide mic", lambda: self.set_dictation_button(not self.dictation_button))
                self.refine_btn = self._action(actions, "Hide pencil", lambda: self.set_refine_button(not self.refine_button))
            if svc == "kokoro":
                # Read aloud's speaker button lives on its own row, next to its voice.
                self.read_btn = self._action(actions, "Hide speaker", lambda: self.set_read_button(not self.read_button))
            toggle = ttk.Button(card, text="Stop", width=BTN_B, command=lambda s=svc: self.toggle(s))
            toggle.grid(row=row, column=4, sticky="ne")
            toggle.grid_remove()   # _render_services shows it where the stack starts and stops the module
            self.row_widgets[svc] = {"dot": dot, "state": state, "toggle": toggle, "role": role_label,
                                     "all": [w for w in (line, dot, names, state, actions) if w is not None]}
            if svc == "ollama":
                self.runner_slots = [self._runner_slot(card, row + 1 + k, k) for k in range(OLLAMA_SLOTS)]
            reason = ttk.Label(card, text="", style="Bad.TLabel", wraplength=480, justify="left")
            reason.grid(row=base + 7, column=1, columnspan=2, sticky="w", pady=(GAP_XS, 0))
            show = ttk.Button(card, text="Show log", width=BTN_A, command=lambda s=svc: self.show_log(s))
            show.grid(row=base + 7, column=3, sticky="ne", padx=(0, GAP_S), pady=(GAP_XS, 0))
            reason.grid_remove()
            show.grid_remove()
            self.reason_widgets[svc] = (reason, show)

    def _runner_slot(self, card, row: int, k: int) -> tuple:
        """A row under Local models for one loaded model's runner process; hidden until Ollama loads that many."""
        names = ttk.Frame(card, style="Card.TFrame")
        names.grid(row=row, column=1, sticky="nw", padx=(GAP_L, 0), pady=(GAP_S, 0))
        name = ttk.Label(names, text="", style="Card.TLabel")
        name.pack(anchor="w")
        detail = ttk.Label(names, text="", style="Card.Muted.TLabel")
        detail.pack(anchor="w")
        state = ttk.Label(card, text="", style="Card.Sub.TLabel")
        state.grid(row=row, column=2, sticky="nw", padx=GAP_M, pady=(GAP_S, 0))
        unload = ttk.Button(card, text="Unload", width=BTN_B)   # its model is bound on every render
        unload.grid(row=row, column=4, sticky="ne", pady=(GAP_S, 0))
        for w in (names, state, unload):
            w.grid_remove()
        return names, name, detail, state, unload

    def _build_gpu(self, body) -> None:
        """One card for the GPU: every model loaded (Ollama, Whisper, ComfyUI), and the switch that hands the card to
        chat or to media (plan G1)."""
        models = self._card(body, "GPU: loaded models", row=1, column=0, pady=(GAP_L, 0))
        models.columnconfigure(0, weight=1)
        self.loaded_frame = ttk.Frame(models, style="Card.TFrame")
        self.loaded_frame.grid(row=1, column=0, columnspan=2, sticky="we")
        self.gpu_text = getattr(self, "gpu_text", "Chat and media share the card: Media before long image or video "
                                "jobs, Chat for fast replies.")
        self.gpu_label = ttk.Label(models, text=self.gpu_text, style="Card.Muted.TLabel", wraplength=640, justify="left")
        self.gpu_label.grid(row=2, column=0, sticky="w", pady=(GAP_S, 0))
        gbtn = ttk.Frame(models, style="Card.TFrame")
        gbtn.grid(row=2, column=1, sticky="e", pady=(GAP_S, 0))
        ttk.Button(gbtn, text="Chat", width=BTN_B, command=lambda: self.set_gpu_mode("chat")).pack(side="left", padx=(0, GAP_XS))
        ttk.Button(gbtn, text="Media", width=BTN_B, command=lambda: self.set_gpu_mode("media")).pack(side="left")

    def _build_features(self, body) -> None:
        """The installer's features: installed, on or off, linked to the stack, what each takes on this PC, and an
        Install, Repair or Remove button that runs the setup worker for that feature alone. Under Local models, every
        model in the installer's catalog (and any other Ollama has), with Download or Remove."""
        card = self._card(body, "Features", row=2, column=0, pady=(GAP_L, 0))
        card.columnconfigure(1, weight=1)
        self.features_card = card
        self.feature_widgets: dict[str, dict] = {}
        self.model_widgets: list = []
        self.model_shown: tuple = ()
        for n, f in enumerate(features.FEATURES):
            base = 100 * n + 1
            line = self._line(card, base) if n else None
            row = base + 1
            dot = tk.Label(card, text="●", font=(FONT, 12), bg=self.t["card"], fg=self.t["muted"])
            dot.grid(row=row, column=0, sticky="n", padx=(0, GAP_S))
            names = ttk.Frame(card, style="Card.TFrame")
            names.grid(row=row, column=1, sticky="nw")
            ttk.Label(names, text=f.title, style="Card.Name.TLabel").pack(anchor="w")
            load = ttk.Label(names, text="", style="Card.Muted.TLabel")
            load.pack(anchor="w")
            detail = ttk.Label(names, text="", style="Card.Muted.TLabel", wraplength=440, justify="left")
            detail.pack(anchor="w", pady=(2, 0))
            state = ttk.Label(card, text="Checking...", style="Card.Sub.TLabel", width=-20)
            state.grid(row=row, column=2, sticky="nw", padx=GAP_M)
            actions = ttk.Frame(card, style="Card.TFrame")
            actions.grid(row=row, column=3, sticky="ne", padx=(0, GAP_S))
            fix = self._action(actions, "Use gateway", self.openclaw_use_gateway) if f.id == "openclaw" else None
            repair = self._action(actions, "Repair", lambda fid=f.id: self.feature_action(fid, repair=True))
            for btn in (fix, repair):
                if btn is not None:
                    btn.pack_forget()
            main = ttk.Button(card, text="Install", width=BTN_B, command=lambda fid=f.id: self.feature_action(fid))
            main.grid(row=row, column=4, sticky="ne")
            main.grid_remove()
            self.feature_widgets[f.id] = {"dot": dot, "load": load, "state": state, "detail": detail, "fix": fix,
                                          "repair": repair, "main": main, "base": base,
                                          "block": [x for x in (line, dot, names, state, actions) if x is not None]}
        foot = ttk.Frame(card, style="Card.TFrame")
        foot.grid(row=100 * len(features.FEATURES) + 1, column=0, columnspan=5, sticky="we", pady=(GAP_M, 0))
        foot.columnconfigure(0, weight=1)
        self.setup_label = ttk.Label(foot, text="", style="Card.Sub.TLabel", wraplength=640, justify="left")
        self.setup_label.grid(row=0, column=0, sticky="w")
        self.setup_bar = ttk.Progressbar(foot, mode="determinate", maximum=1.0)
        self.setup_bar.grid(row=1, column=0, columnspan=2, sticky="we", pady=(GAP_XS, GAP_S))
        self.setup_label.grid_remove()
        self.setup_bar.grid_remove()
        self.features_note = ttk.Label(foot, text="", style="Card.Muted.TLabel", wraplength=640, justify="left")
        self.features_note.grid(row=2, column=0, sticky="w")
        self.add_features_btn = ttk.Button(foot, text="Open installer...", command=self.open_installer)
        self.add_features_btn.grid(row=2, column=1, sticky="e", padx=(GAP_S, 0))

    def _build_storage(self, body) -> None:
        """Storage: everything the stack keeps on disk, as a thin bar split into models, programs and data, a total
        per drive, and the breakdown below (stacklib/storage.py). Measured in a thread, on opening and on Refresh."""
        t = self.t
        card = self._card(body, None, row=3, column=0, pady=(GAP_L, 0))
        card.columnconfigure(0, weight=1)
        head = ttk.Frame(card, style="Card.TFrame")
        head.grid(row=0, column=0, sticky="we")
        head.columnconfigure(0, weight=1)
        ttk.Label(head, text="Storage", style="Card.Title.TLabel").grid(row=0, column=0, sticky="w")
        self.storage_note = ttk.Label(head, text="", style="Card.Muted.TLabel")
        self.storage_note.grid(row=0, column=1, sticky="e", padx=(0, GAP_S))
        self.storage_btn = ttk.Button(head, text="Refresh", width=BTN_B, command=lambda: self.scan_storage(force=True))
        self.storage_btn.grid(row=0, column=2, sticky="e")
        self.storage_total = ttk.Label(card, text="Measuring what the stack keeps on disk...", style="Card.TLabel",
                                       wraplength=820, justify="left")
        self.storage_total.grid(row=1, column=0, sticky="w", pady=(GAP_S, 0))
        self.storage_bar = tk.Canvas(card, height=STORAGE_BAR_PX, bg=t["card"], highlightthickness=0)
        self.storage_bar.grid(row=2, column=0, sticky="we", pady=(GAP_S, GAP_S))
        self.storage_bar.bind("<Configure>", lambda _e: self._draw_storage_bar())
        legend = ttk.Frame(card, style="Card.TFrame")
        legend.grid(row=3, column=0, sticky="w")
        self.storage_legend: dict[str, ttk.Label] = {}
        colors = STORAGE_COLORS[system_theme()]
        for i, group in enumerate(storage.GROUPS):
            tk.Label(legend, text="■", font=(FONT, 11), bg=t["card"], fg=colors[i]).pack(side="left", padx=(0 if i == 0 else GAP_L, GAP_XS))
            self.storage_legend[group] = ttk.Label(legend, text=group, style="Card.TLabel")
            self.storage_legend[group].pack(side="left")
        cols = (("size", "Size", 80, "e"), ("note", "Note", 250, "w"), ("where", "Where", 210, "w"))
        self.storage_tree = ttk.Treeview(card, columns=[c[0] for c in cols], show="tree headings", selectmode="browse",
                                         height=4)
        self.storage_tree.heading("#0", text="What", anchor="w")
        self.storage_tree.column("#0", width=290, minwidth=200, anchor="w", stretch=True)
        for key, title, width, anchor in cols:
            self.storage_tree.heading(key, text=title, anchor=anchor)
            self.storage_tree.column(key, width=width, minwidth=60, anchor=anchor, stretch=key == "where")
        self.storage_tree.grid(row=4, column=0, sticky="we", pady=(GAP_M, 0))
        self.storage_tree.tag_configure("group", font=(FONT, 10, "bold"))
        self.storage_tree.tag_configure("off", foreground=t["muted"])
        self.storage_tree.tag_configure("warn", foreground=t["warn"])
        self.storage_tree.bind("<<TreeviewSelect>>", lambda _e: self._storage_selected())
        self.storage_tree.bind("<Double-1>", lambda _e: self.open_storage_folder())
        self.storage_tree.bind("<Return>", lambda _e: self.open_storage_folder())
        self.storage_tree.bind("<<TreeviewOpen>>", lambda _e: self.root.after_idle(self._fit_storage_tree))
        self.storage_tree.bind("<<TreeviewClose>>", lambda _e: self.root.after_idle(self._fit_storage_tree))
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):   # the page scrolls; the table shows every row
            self.storage_tree.bind(seq, lambda e: (self._wheel(e), "break")[1])
        foot = ttk.Frame(card, style="Card.TFrame")
        foot.grid(row=5, column=0, sticky="we", pady=(GAP_S, 0))
        foot.columnconfigure(1, weight=1)
        self.storage_open_btn = ttk.Button(foot, text="Open folder", command=self.open_storage_folder, state="disabled")
        self.storage_open_btn.grid(row=0, column=0, sticky="w")
        self.storage_problems = ttk.Label(foot, text="", style="Card.Muted.TLabel", wraplength=640, justify="left")
        self.storage_problems.grid(row=0, column=1, sticky="w", padx=(GAP_M, 0))

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
        self._render_features()
        self._render_storage()
        if any(r["state"] == "starting" for r in self.rows.values()):
            self._tick_soon()

    def _render_services(self) -> None:
        """Service rows, the status pill and Start all / Stop all, from cached state only (no I/O): runs on every
        click and once a second while something is starting or stopping."""
        if not self._window_built():
            return
        t = self.t
        up = 0
        for svc, w in self.row_widgets.items():
            dot, state, toggle = w["dot"], w["state"], w["toggle"]
            if self._kokoro_in_app(svc):
                level, text, _role = features.read_aloud_row(self.profile, self.dictation_health,
                                                             self.feature_status.get("read_aloud"))
                dot.configure(fg=t[{"off": "muted"}.get(level, level)])
                state.configure(text=text, style="Warn.TLabel" if level in ("warn", "bad") else "Card.Sub.TLabel")
                w["role"].configure(text=self._role(svc))
                toggle.grid_remove()   # read aloud starts and stops with voice typing
                continue
            row = self.rows.get(svc, {})
            healthy = bool(row.get("healthy"))
            enabled = svc == "ollama" or svc in self.managed
            up += healthy and enabled
            pid = self.ollama_tree.get("pid") if svc == "ollama" else row.get("pid")
            pending = self.pending.get(svc)
            installed = features.service_installed(svc, self.feature_status)  # None until the first feature check
            if pending:
                dot.configure(fg=t["warn"])
                verb = "Starting" if pending[0] == "start" else "Stopping"
                state.configure(text=verb + waited(time.monotonic() - pending[1]), style="Warn.TLabel")
            elif healthy:
                dot.configure(fg=t["good"])
                state.configure(text=f"Running{f'  ·  pid {pid}' if pid else ''}", style="Card.Sub.TLabel")
            elif row.get("state") == "starting":  # the process is alive but does not answer yet
                created = self._created(pid)
                dot.configure(fg=t["warn"])
                state.configure(text="Starting" + waited(created and time.time() - created), style="Warn.TLabel")
            elif installed is False:  # its feature was not installed: Start would only fail
                dot.configure(fg=t["warn"] if enabled else t["muted"])
                state.configure(text="Not installed", style="Warn.TLabel" if enabled else "Card.Sub.TLabel")
            elif svc == "ollama":
                dot.configure(fg=t["bad"])
                state.configure(text="Not running", style="Card.Sub.TLabel")
            elif enabled:
                dot.configure(fg=t["bad"])
                state.configure(text="Stopped", style="Card.Sub.TLabel")
            elif svc in features.NOT_INSTALLABLE:
                dot.configure(fg=t["muted"])
                state.configure(text="Not available yet", style="Card.Sub.TLabel")
            else:
                dot.configure(fg=t["muted"])
                state.configure(text="Off in settings", style="Card.Sub.TLabel")
            if svc == "ollama":
                # The Ollama app runs it, not the stack: Start only brings it back when it is down.
                if pending or not healthy:
                    toggle.configure(text="Start", state="disabled" if pending or self.busy else "normal")
                    toggle.grid()
                else:
                    toggle.grid_remove()
            else:
                stopping = bool(pending) and pending[0] == "stop"
                startable = (enabled and installed is not False) or healthy or self._running(svc)
                if startable or self._running(svc):
                    toggle.configure(text="Stop" if self._running(svc) else "Start",
                                     state="disabled" if self.busy or stopping or self._setup_owns(svc) else "normal")
                    toggle.grid()
                else:
                    toggle.grid_remove()   # off in Settings or not installed: nothing to start here
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
        self._render_runners()
        for attr, shown, name in (("dictation_btn", self.dictation_button, "mic"),
                                  ("refine_btn", self.refine_button, "pencil"),
                                  ("read_btn", self.read_button, "speaker")):
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
        can_start = any(not self._running(s) and s not in self.pending and not self._setup_owns(s) for s in self.managed)
        can_stop = any(self._running(s) and self.pending.get(s, ("",))[0] != "stop" and not self._setup_owns(s)
                       for s in self.managed)
        self.start_btn.configure(state="normal" if can_start and not self.busy else "disabled")
        self.stop_btn.configure(state="normal" if can_stop and not self.busy else "disabled")

    def _render_runners(self) -> None:
        """One row per model Ollama has loaded, each in its own runner process: name, context, GPU memory, its pid."""
        runners = self.ollama_tree.get("runners") or []
        sizes = {str(m.get("name")): m for m in self.loaded}
        for k, (names, name, detail, state, unload) in enumerate(self.runner_slots):
            r = runners[k] if k < len(runners) else None
            if r is None:
                for w in (names, state, unload):
                    w.grid_remove()
                continue
            m = sizes.get(r["model"], {})
            ctx = int(m.get("context_length") or r.get("context") or 0)
            vram = int(m.get("size_vram") or 0)
            bits = ["model runner"] + ([f"{ctx // 1024}k context"] if ctx else []) + \
                   ([f"{human_bytes(vram)} on the GPU"] if vram else [])
            name.configure(text=r["model"])
            detail.configure(text="  ·  ".join(bits))
            leaving = r["model"] in self.unloading
            state.configure(text="Unloading..." if leaving else f"Loaded  ·  pid {r['pid']}",
                            style="Warn.TLabel" if leaving else "Card.Sub.TLabel")
            unload.configure(state="disabled" if leaving or r["model"] not in sizes else "normal",
                             command=lambda name=r["model"]: self.unload_model(name))
            for w in (names, state, unload):
                w.grid()

    def unload_model(self, name: str) -> None:
        """Unload one model from Ollama (keep_alive 0); the next request that needs it loads it again."""
        if name in self.unloading:
            return
        self.unloading.add(name)
        self._render_runners()

        def run() -> None:
            try:
                ok = media.unload_model(self.profile, name)
                print(f"[tray] unload {name}: {'done' if ok else 'Ollama did not answer'}")
                self.refresh()
            finally:
                self.ui_queue.put(lambda: (self.unloading.discard(name), self._render_runners()))

        threading.Thread(target=run, daemon=True, name="unload-model").start()

    def start_ollama(self) -> None:
        """Start the Ollama app when it is down (it is the Ollama app's server, not one of the stack's services)."""
        if "ollama" in self.pending:
            return
        entry = ("start", time.monotonic())
        self.pending["ollama"] = entry
        self.problems.pop("ollama", None)
        self._render_services()
        self._tick_soon()
        base = f"http://127.0.0.1:{self.profile['ports']['ollama']}"

        def run() -> None:
            problem = None
            try:
                ollama.restart(base)
                if not ollama.version(base):
                    problem = ("Ollama did not answer within 30 s. Start it from the Start menu.", ollama_log())
            except Exception as e:  # noqa: BLE001 - shown on the row
                problem = (f"Could not start Ollama: {e}", ollama_log())
            checked = time.monotonic()
            row = services.probe(self.profile, "ollama")
            self.ui_queue.put(lambda: self._action_done("ollama", entry, row, checked, problem))

        threading.Thread(target=run, daemon=True, name="start-ollama").start()

    def _level_look(self, level: str) -> tuple[str, str]:
        """(dot colour, state label style) for a status level: ok, warn, bad or off."""
        t = self.t
        return ({"ok": t["good"], "warn": t["warn"], "bad": t["bad"]}.get(level, t["muted"]),
                {"warn": "Warn.TLabel", "bad": "Bad.TLabel"}.get(level, "Card.Sub.TLabel"))

    # ---------- Features: install, repair, remove ----------
    def _setup_running(self) -> bool:
        return self.setup_state.get("status") == "running"

    def _setup_step(self) -> dict | None:
        return next((s for s in self.setup_state.get("steps") or [] if s.get("status") == "running"), None)

    def _feature_busy(self, fid: str) -> str:
        """"Installing", "Repairing", "Removing", "Downloading" or "" for a feature the setup worker works on now."""
        if fid in self.feature_starting:
            return self.feature_starting[fid]
        st = self.setup_state
        if st.get("status") != "running" or fid not in (st.get("targets") or []):
            return ""
        sid = str((self._setup_step() or {}).get("id") or "")
        return "Removing" if sid.startswith("remove") else "Downloading" if sid == "pull_more" else "Installing"

    @staticmethod
    def _feature_buttons(fid: str, s) -> tuple[bool, str]:
        """(Repair shown in the first action column?, the second column's button: Install, Remove, or ""). A feature
        no longer offered has Remove only, while something of it is on this PC."""
        f = features.BY_ID[fid]
        if s is None or s.unknown:
            return False, ""
        if not f.offered:
            return False, "Remove" if features.present(fid, {fid: s}) else ""
        repair = s.state in REPAIR_STATES
        if f.required:
            return repair, "" if s.installed or repair else "Install"
        if s.installed or repair:
            return repair, "Remove"
        return False, "Install"

    def _render_features(self) -> None:
        """The Features card, from the last feature check (once a minute), the setup worker's state and OpenClaw's Use
        gateway state."""
        if not self._window_built() or not hasattr(self, "feature_widgets"):
            return
        t = self.t
        status = self.feature_status
        running = self._setup_running()
        for fid, w in self.feature_widgets.items():
            f, s, e = features.BY_ID[fid], status.get(fid), self.feature_est.get(fid)
            if e:
                w["load"].configure(text=("Required  ·  " if f.required else "") + features.brief(e))
            listed = f.offered or (s is not None and features.present(fid, status)) or bool(self._feature_busy(fid))
            for widget in w["block"]:   # a feature no longer offered shows only while something of it is here
                widget.grid() if listed else widget.grid_remove()
            if not listed:
                w["main"].grid_remove()
                continue
            busy = self._feature_busy(fid)
            if busy:
                step = self._setup_step()
                w["dot"].configure(fg=t["warn"])
                w["state"].configure(text=f"{busy}...", style="Warn.TLabel")
                w["detail"].configure(text=(step or {}).get("detail") or "Waiting for the setup worker...")
            elif fid == "openclaw" and self.openclaw_busy:
                w["dot"].configure(fg=t["warn"])
                w["state"].configure(text="Setting up...", style="Warn.TLabel")
            elif s:
                fg, style = self._level_look(s.level)
                w["dot"].configure(fg=fg)
                w["state"].configure(text=s.state, style=style)
                extra = self.openclaw_result + "  " if fid == "openclaw" and self.openclaw_result else ""
                w["detail"].configure(text=uninstall.short_text(extra + s.detail))
            blocked = running or bool(self.busy) or bool(self.feature_starting)
            show_repair, label = self._feature_buttons(fid, s)
            # The first column, in a fixed order: Use gateway (OpenClaw installed but not gateway-only; a failure
            # keeps it up so the owner can retry), then Repair.
            fix, repair = w["fix"], w["repair"]
            for btn in (fix, repair):
                if btn is not None:
                    btn.pack_forget()
            if fix is not None and (self.openclaw_busy or (s and s.installed and not s.on and s.state != "Not checked")):
                fix.configure(state="disabled" if self.openclaw_busy or blocked else "normal")
                fix.pack(side="top", fill="x", pady=(0, GAP_XS))
            if show_repair and not busy:
                repair.configure(state="disabled" if blocked else "normal")
                repair.pack(side="top", fill="x", pady=(0, GAP_XS))
            if label and not busy:
                w["main"].configure(text=label, state="disabled" if blocked else "normal")
                w["main"].grid()
            else:
                w["main"].grid_remove()
        self._render_models()
        self._render_setup()
        missing = [features.BY_ID[fid].short for fid in features.not_installed(status)]
        if not status:
            note = "Checking which features are installed..."
        elif running:
            note = "One setup runs at a time: Install and Remove wait until this one finishes."
        else:
            note = ("Install and Remove use the folders the installer chose before; Open installer changes folders and "
                    "options, and shows what each feature costs on this PC." if missing else
                    "Every feature is installed. Remove takes one off again; Settings turns one off without removing it.")
        self.features_note.configure(text=f"{self.installer_note}  {note}" if self.installer_note else note)

    def _render_models(self) -> None:
        """The rows under Local models: every model in the catalog and any other Ollama has, with Download or Remove.
        Rebuilt only when the list changes; buttons follow the setup worker on every render."""
        w = self.feature_widgets.get("models")
        if w is None:
            return
        rows = self.model_rows
        shape = tuple((m.name, m.downloaded, m.use, round(m.size_gb, 1)) for m in rows)
        card = self.features_card
        if shape != self.model_shown:
            for widget in self.model_widgets:
                widget.destroy()
            self.model_widgets, self.model_buttons = [], {}
            for i, m in enumerate(rows):
                r = w["base"] + 2 + i
                names = ttk.Frame(card, style="Card.TFrame")
                names.grid(row=r, column=1, sticky="nw", padx=(GAP_L, 0), pady=(GAP_S if i == 0 else GAP_XS, 0))
                ttk.Label(names, text=m.name, style="Card.TLabel").pack(anchor="w")
                ttk.Label(names, text=model_line(m), style="Card.Muted.TLabel").pack(anchor="w")
                size = ttk.Label(card, text=f"{m.size_gb:.1f} GB" + ("" if m.downloaded else " download"),
                                 style="Card.Sub.TLabel")
                size.grid(row=r, column=2, sticky="nw", padx=GAP_M, pady=(GAP_S if i == 0 else GAP_XS, 0))
                btn = ttk.Button(card, text="Remove" if m.downloaded else "Download", width=BTN_B,
                                 command=lambda m=m: self.model_action(m))
                btn.grid(row=r, column=4, sticky="ne", pady=(GAP_S if i == 0 else GAP_XS, 0))
                self.model_widgets += [names, size, btn]
                self.model_buttons[m.name] = (btn, m)
            self.model_shown = shape
        running = self._setup_running()
        for btn, m in getattr(self, "model_buttons", {}).values():
            blocked = running or self.busy or bool(self.feature_starting) or (m.downloaded and bool(m.use))
            btn.configure(state="disabled" if blocked else "normal")

    def _render_setup(self) -> None:
        """The line under the features while the setup worker runs (or just ran): its step, and a measure."""
        st = self.setup_state
        status = st.get("status")
        if not st or status not in ("running", "failed", "warnings", "interrupted") or not self.setup_watch:
            self.setup_label.grid_remove()
            self.setup_bar.stop()
            self.setup_bar.grid_remove()
            return
        steps = st.get("steps") or []
        if status == "running":
            step = self._setup_step()
            n = [s.get("id") for s in steps].index(step["id"]) + 1 if step else 0
            text = (f"Setup, step {n} of {len(steps)}: {step['title']}" + (f": {step['detail']}" if step.get("detail") else "")
                    if step else "Setup is starting...")
            self.setup_label.configure(text=uninstall.short_text(text), style="Card.Sub.TLabel")
            frac = step.get("fraction") if step else None
            if frac is not None:
                if str(self.setup_bar.cget("mode")) != "determinate":
                    self.setup_bar.stop()
                    self.setup_bar.configure(mode="determinate")
                self.setup_bar["value"] = frac
            elif str(self.setup_bar.cget("mode")) != "indeterminate":
                self.setup_bar.configure(mode="indeterminate")
                self.setup_bar.start(15)
            self.setup_bar.grid()
            if self.setup_job is None:   # follow the worker every second while it runs, not only every poll
                self.setup_job = self.root.after(1000, self._setup_tick)
        else:
            bad = [s for s in steps if s.get("status") in ("failed", "warning")]
            text = install.summary(st) + " " + " ".join(f"{s['title']}: {s.get('detail') or s['status']}." for s in bad[:3])
            self.setup_label.configure(text=uninstall.short_text(text.strip()), style="Warn.TLabel")
            self.setup_bar.stop()
            self.setup_bar.grid_remove()
        self.setup_label.grid()

    def _setup_tick(self) -> None:
        """Once a second while the setup worker runs: read its state file (a few hundred bytes) and redraw the
        features. When it has ended, the poll handles the end at once (_check_setup)."""
        self.setup_job = None
        if not self._window_built():
            return
        self._set_setup_state(install.read_state(), time.monotonic())
        self._render_features()
        self._render_services()
        if self.setup_state.get("status") != "running":
            self.refresh_soon()

    def feature_action(self, fid: str, repair: bool = False) -> None:
        """Install, Repair or Remove on a feature row. Install and Repair run at once (setup only adds); Remove asks
        first, with what it deletes and what it keeps."""
        s = self.feature_status.get(fid)
        show_repair, label = self._feature_buttons(fid, s)
        if self._setup_running() or self.feature_starting or (repair and not show_repair) or (not repair and not label):
            return
        if label == "Remove" and not repair:
            self._ask_remove(fid)
            return
        f = features.BY_ID[fid]
        needs_folder = any(features.BY_ID[x].needs_media for x in features.with_requirements({fid})) \
            and not (self.profile.get("media") or {}).get("root")
        if needs_folder or (fid == "models" and s and s.state == "Not installed"):
            self.installer_note = (f"{f.short[0].upper()}{f.short[1:]} needs a folder (or a program) the installer "
                                   "asks for: opening it.")
            self.open_installer()
            return
        self._start_setup(fid, "Repairing" if repair else "Installing",
                          lambda: install.start_feature(self.profile, fid, self.feature_status))

    def _start_setup(self, fid: str, verb: str, start) -> None:
        """Run `start` (it spawns the setup worker) off the Tk thread; the row says so at once."""
        self.feature_starting[fid] = verb
        self.setup_watch = True
        self._render_features()

        def run() -> None:
            note = ""
            try:
                pid = start()
                print(f"[tray] setup worker pid {pid} for {fid} ({verb.lower()})")
            except Exception as e:  # noqa: BLE001 - any failure: say so on the card, never leave the buttons locked
                traceback.print_exc()
                note = f"Could not start setup: {e}"
            finally:
                read_at, state = time.monotonic(), install.read_state()

                def done() -> None:
                    self._set_setup_state(state, read_at)
                    self.feature_starting.pop(fid, None)
                    self.installer_note = note
                    self._render_features()
                    self._render_services()
                self.ui_queue.put(done)

        threading.Thread(target=run, daemon=True, name=f"setup-{fid}").start()

    def _ask_remove(self, fid: str) -> None:
        """Measure what removing the feature deletes (seconds for a big folder), then ask."""
        f = features.BY_ID[fid]
        btn = self.feature_widgets[fid]["main"]
        btn.configure(text="Checking...", state="disabled")

        def run() -> None:
            try:
                plan = uninstall.plan(self.profile, fid, self.feature_status)
            except Exception as e:  # noqa: BLE001 - shown in the dialog
                plan = uninstall.Removal(fid, f.title, blocked=f"Could not check what it would delete: {e}")

            def ask() -> None:
                self._render_features()
                if not self._window_built():
                    return
                if self.window.state() != "normal":   # closed (hidden) while the folders were measured
                    self.window.deiconify()
                    self.window.lift()
                if plan.blocked:
                    self._notice(f"{f.title} cannot be removed now", plan.blocked)
                    return
                size = f", about {uninstall.features_gb(plan.size_gb)}" if plan.size_gb >= 0.01 else ""
                self._confirm(f"Remove {f.short}?", f"This removes {f.title} from this PC{size}.\n\n{plan.text()}",
                              f"Remove {f.short}", lambda: self._start_setup(
                                  fid, "Removing", lambda: install.start_removal(self.profile, [fid])),
                              cancel="Keep it")
            self.ui_queue.put(ask)

        threading.Thread(target=run, daemon=True, name=f"plan-remove-{fid}").start()

    def model_action(self, m) -> None:
        """Download or Remove on a model row under Local models. Removing asks first; a download checks the space."""
        if self._setup_running() or self.feature_starting:
            return
        if m.downloaded:
            if m.use:
                return
            where = features.effective_model_store(self.profile)
            self._confirm(f"Delete {m.name}?",
                          f"This deletes the model {m.name} from {uninstall.short_path(where)} and frees about "
                          f"{m.size_gb:.1f} GB. The stack does not use it now; you can download it again from this list.",
                          "Delete model", lambda: self._start_setup(
                              "models", "Removing", lambda: install.start_removal(self.profile, models=[m.name])),
                          cancel="Keep it")
            return
        store = features.effective_model_store(self.profile)
        free = storage.free_bytes(storage.drive_of(store))
        if free is not None and free / 1e9 < m.size_gb + 1:
            self._notice(f"Not enough space for {m.name}",
                         f"{m.name} needs about {m.size_gb:.1f} GB, and {storage.drive_of(store)} has "
                         f"{free / 1e9:.1f} GB free. Free some space, or move the models folder in the installer.")
            return
        self._start_setup("models", "Downloading", lambda: install.start_download(self.profile, [m.name]))

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
                self._render_features()
            self._on_ui(done)
        threading.Thread(target=run, daemon=True, name="openclaw-setup").start()

    # ---------- dialogs ----------
    def _dialog(self, title: str) -> tuple[tk.Toplevel, ttk.Frame]:
        """A small modal window over the status window, in the window's theme."""
        t = self.t
        d = tk.Toplevel(self.window, bg=t["card"])
        d.withdraw()
        d.title(title)
        d.transient(self.window)
        d.resizable(False, False)
        dark_title_bar(d)
        frame = ttk.Frame(d, style="Card.TFrame", padding=GAP_XL)
        frame.pack(fill="both", expand=True)
        return d, frame

    def _show_dialog(self, d: tk.Toplevel, focus) -> None:
        d.update_idletasks()
        w = self.window
        x = w.winfo_rootx() + max(0, (w.winfo_width() - d.winfo_reqwidth()) // 2)
        y = w.winfo_rooty() + max(0, (w.winfo_height() - d.winfo_reqheight()) // 3)
        d.geometry(f"+{x}+{y}")
        d.deiconify()
        d.lift()

        def grab(tries: int = 10) -> None:
            try:
                d.grab_set()
            except tk.TclError:   # not viewable yet: try again in a moment
                if tries and d.winfo_exists():
                    d.after(50, lambda: grab(tries - 1))
        grab()
        focus.focus_set()

    def _confirm(self, title: str, body: str, action: str, on_yes, cancel: str = "Cancel", danger: bool = True) -> None:
        """Ask before something costly or irreversible (ERR-03): the title names the object, the body says what
        happens to what, the buttons are verbs, and the safe choice has the focus, so Enter or Esc keep things as
        they are."""
        d, frame = self._dialog(title)
        ttk.Label(frame, text=title, style="Card.Title.TLabel").pack(anchor="w")
        ttk.Label(frame, text=body, style="Card.TLabel", wraplength=520, justify="left").pack(anchor="w", pady=(GAP_S, GAP_L))
        buttons = ttk.Frame(frame, style="Card.TFrame")
        buttons.pack(fill="x")

        def close() -> None:
            d.grab_release()
            d.destroy()

        def yes() -> None:
            close()
            on_yes()

        keep = ttk.Button(buttons, text=cancel, command=close)
        keep.pack(side="right")
        go = ttk.Button(buttons, text=action, style="Danger.TButton" if danger else "TButton", command=yes)
        go.pack(side="right", padx=(0, GAP_S))
        d.bind("<Escape>", lambda _e: close())
        d.bind("<Return>", lambda e: e.widget.invoke() if isinstance(e.widget, ttk.Button) else close())
        d.protocol("WM_DELETE_WINDOW", close)
        self._show_dialog(d, keep)

    def _notice(self, title: str, body: str) -> None:
        """Say why something cannot be done now, with one button to close."""
        d, frame = self._dialog(title)
        ttk.Label(frame, text=title, style="Card.Title.TLabel").pack(anchor="w")
        ttk.Label(frame, text=body, style="Card.TLabel", wraplength=520, justify="left").pack(anchor="w", pady=(GAP_S, GAP_L))

        def close() -> None:
            d.grab_release()
            d.destroy()

        ok = ttk.Button(frame, text="Close", command=close)
        ok.pack(side="right")
        d.bind("<Escape>", lambda _e: close())
        d.bind("<Return>", lambda _e: close())
        d.protocol("WM_DELETE_WINDOW", close)
        self._show_dialog(d, ok)

    # ---------- Storage ----------
    def scan_storage(self, force: bool = False) -> None:
        """Measure what the stack keeps on disk, in a thread (a few seconds: it walks every file). Without force,
        only when the last scan is older than STORAGE_SECONDS."""
        if self.storage_busy or not self._window_built():
            return
        if not force and self.storage and time.time() - self.storage.at < STORAGE_SECONDS:
            return
        self.storage_busy = True
        self._render_storage()

        def run() -> None:
            try:
                result, error = storage.scan(self.profile, self.feature_status or None), ""
            except Exception as e:  # noqa: BLE001 - the card says what failed and keeps the last scan
                traceback.print_exc()
                result, error = None, str(e) or type(e).__name__

            def done() -> None:
                self.storage_busy = False
                if result is not None:
                    self.storage = result
                self.storage_error = error
                self._render_storage()
            self.ui_queue.put(done)

        threading.Thread(target=run, daemon=True, name="storage-scan").start()

    def _render_storage(self) -> None:
        if not self._window_built() or not hasattr(self, "storage_tree"):
            return
        s = self.storage
        self.storage_btn.configure(state="disabled" if self.storage_busy else "normal")
        if self.storage_busy:
            self.storage_note.configure(text="Measuring...")
        elif s:
            self.storage_note.configure(text=f"Measured {datetime.fromtimestamp(s.at):%H:%M} in {s.took_s:.0f} s")
        if s is None:
            if self.storage_error:
                self.storage_total.configure(text=f"Could not measure: {self.storage_error}", style="Warn.TLabel")
            return
        drives = []
        for drive, used in s.by_drive().items():
            free = storage.free_bytes(drive)
            drives.append(f"{drive} {storage.size_text(used)}" + (f" ({storage.size_text(free)} free)" if free is not None else ""))
        self.storage_total.configure(text=f"The stack keeps {storage.size_text(s.total())} on this PC: " + "  ·  ".join(drives),
                                     style="Card.TLabel")
        for group, label in self.storage_legend.items():
            label.configure(text=f"{group} {storage.size_text(s.total(group))}")
        tree = self.storage_tree
        was_open = {i: tree.item(i, "open") for i in tree.get_children()}
        sel = tree.selection()
        keep = sel[0] if sel else None
        tree.delete(*tree.get_children())
        for group in storage.GROUPS:
            entries = sorted((e for e in s.entries if e.group == group), key=lambda e: -e.bytes)
            if not entries:
                continue
            tree.insert("", "end", iid=group, text=group, values=(storage.size_text(s.total(group)), "", ""),
                        tags=("group",), open=was_open.get(group, True))
            for i, e in enumerate(entries):
                tree.insert(group, "end", iid=f"{group}:{i}", text=e.name,
                            values=(storage.size_text(e.bytes) if e.bytes else "-", e.note, uninstall.short_path(e.path)),
                            tags=(e.level,) if e.level in ("off", "warn") else ())
        if keep and tree.exists(keep):
            tree.selection_set(keep)
        self._fit_storage_tree()
        self._storage_selected()
        problems = list(s.problems) + ([f"Last refresh failed: {self.storage_error}"] if self.storage_error else [])
        self.storage_problems.configure(text=" ".join(problems) or "Double-click a row (or Open folder) to see it in "
                                                                     "Explorer. Remove features or models above to free space.")
        self._draw_storage_bar()

    def _fit_storage_tree(self) -> None:
        """Show every visible row: the page scrolls, not the table."""
        tree = self.storage_tree
        n = sum(1 + (len(tree.get_children(g)) if tree.item(g, "open") else 0) for g in tree.get_children())
        tree.configure(height=max(3, n))

    def _storage_path(self) -> Path | None:
        sel = self.storage_tree.selection()
        if not sel or ":" not in sel[0] or not self.storage:
            return None
        group, _, i = sel[0].partition(":")
        entries = sorted((e for e in self.storage.entries if e.group == group), key=lambda e: -e.bytes)
        p = Path(entries[int(i)].path)
        return p.parent if p.is_file() else p

    def _storage_selected(self) -> None:
        self.storage_open_btn.configure(state="normal" if self._storage_path() else "disabled")

    def open_storage_folder(self) -> None:
        p = self._storage_path()
        if p is not None and p.exists():
            self.open_path(p)

    def _draw_storage_bar(self) -> None:
        """A thin bar split into models, programs and data (no text: the legend and the table carry the figures),
        2 px card-coloured gaps between the parts, rounded outer ends."""
        c = self.storage_bar
        c.delete("all")
        s = self.storage
        total = s.total() if s else 0
        w, h = max(c.winfo_width(), 100), STORAGE_BAR_PX
        if not total:
            self._pill(c, 0, 0, w, h, self.t["grid"], True, True)
            return
        colors = STORAGE_COLORS[system_theme()]
        parts = [(s.total(g), colors[i]) for i, g in enumerate(storage.GROUPS) if s.total(g)]
        x = 0.0
        for i, (size, color) in enumerate(parts):
            seg = w * size / total
            x1 = w if i == len(parts) - 1 else x + seg - 2   # the 2 px gap in the card colour
            if x1 - x >= 1:
                self._pill(c, x, 0, x1, h, color, i == 0, i == len(parts) - 1)
            x += seg

    @staticmethod
    def _pill(c: tk.Canvas, x0: float, y0: float, x1: float, y1: float, fill: str, round_left: bool, round_right: bool) -> None:
        r = (y1 - y0) / 2
        left = x0 + (r if round_left else 0)
        right = x1 - (r if round_right else 0)
        if right > left:
            c.create_rectangle(left, y0, right, y1, fill=fill, width=0)
        if round_left:
            c.create_oval(x0, y0, x0 + 2 * r, y1, fill=fill, width=0)
        if round_right:
            c.create_oval(x1 - 2 * r, y0, x1, y1, fill=fill, width=0)

    def _render_loaded(self) -> None:
        for child in self.loaded_frame.winfo_children():
            child.destroy()
        if not self.gpu_rows:
            ttk.Label(self.loaded_frame, text="No model is loaded. The first request loads one (this can take a minute or two).",
                      style="Card.Muted.TLabel").grid(row=0, column=0, sticky="w")
            return
        for c, h in enumerate(("Model", "Used by", "Size", "On GPU", "Context", "Unloads")):
            ttk.Label(self.loaded_frame, text=h, style="Card.Muted.TLabel").grid(row=0, column=c, sticky="w", padx=(0, 24))
        for r, m in enumerate(self.gpu_rows, start=1):
            size = ("~" if m["estimate"] else "") + human_bytes(m["bytes"]) if m["bytes"] else "-"
            vals = (m["name"], m["by"], size, m["gpu"], compact(m["context"]) if m["context"] else "-", m["unloads"])
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
            c.create_text(left - 8, y, text=label, anchor="e", fill=t["muted"], font=(FONT, 9))
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
                c.create_text((x0 + x1) / 2, h - 8, text=label, fill=t["muted"], font=(FONT, 9))

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
        """One card per group of settings, each with a line on what the group is for. In a card, each setting has its
        name and help on the left and its control on the right, with a hairline between settings."""
        self.tabs.add(tab, text="Settings")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)
        holder, page = self._scroll_area(tab, tab, self.t["page"])
        holder.grid(row=0, column=0, sticky="nsew")
        page.columnconfigure(0, weight=1)
        self.form = page

        self.setting_vars: dict[str, tk.Variable | TextVar] = {}
        self.model_boxes: list[ttk.Combobox] = []
        self.changed_marks: dict[str, ttk.Label] = {}
        self.default_buttons: dict[str, tuple[ttk.Button, object]] = {}  # "text" settings: Restore default
        self.advanced_parts: list[dict] = []
        for i, (title, sections, about) in enumerate(SETTING_GROUPS):
            card = self._card(page, None, row=i, column=0, pady=(0 if i == 0 else GAP_L, 0))
            card.columnconfigure(0, weight=1)
            card.columnconfigure(1, minsize=SETTING_CONTROL_W)   # the controls line up from card to card
            ttk.Label(card, text=title, style="Card.Title.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
            ttk.Label(card, text=about, style="Card.Muted.TLabel", wraplength=760, justify="left").grid(
                row=1, column=0, columnspan=3, sticky="w", pady=(2, GAP_XS))
            row = 2
            in_group = [s for s in cfg.SETTINGS if s.section in (sections if isinstance(sections, tuple) else (sections,))]
            for n, s in enumerate(x for x in in_group if not x.advanced):
                row = self._add_setting(card, s, row, line=n > 0)
            if any(s.advanced for s in in_group):
                row = self._build_advanced(card, row, [s for s in in_group if s.advanced])
            if title == "Models":
                self.cloud_label = ttk.Label(card, text="", style="Card.Muted.TLabel", wraplength=760, justify="left")
                self.cloud_label.grid(row=row, column=0, columnspan=3, sticky="w", pady=(GAP_S, 0))
                self.settings_warning = ttk.Label(card, text="", style="Warn.TLabel", wraplength=760, justify="left")
                self.settings_warning.grid(row=row + 1, column=0, columnspan=3, sticky="w")
                row += 2

        bar = ttk.Frame(tab, padding=(0, GAP_M, 0, 0))
        bar.grid(row=1, column=0, sticky="we")
        bar.columnconfigure(0, weight=1)
        self.pending_label = ttk.Label(bar, text="", style="HeadSub.TLabel", wraplength=520, justify="left")
        self.pending_label.grid(row=0, column=0, sticky="w")
        ttk.Button(bar, text="Open profile file", command=lambda: self.open_path(prof.machine_file(self.profile["name"]))).grid(row=0, column=1, padx=GAP_XS)
        self.revert_btn = ttk.Button(bar, text="Revert", command=self._load_settings)
        self.revert_btn.grid(row=0, column=2, padx=GAP_XS)
        self.apply_btn = ttk.Button(bar, text="Apply", style="Accent.TButton", command=self._apply_settings)
        self.apply_btn.grid(row=0, column=3)
        self.apply_log = ttk.Label(bar, text="", style="HeadSub.TLabel", wraplength=820, justify="left")
        self.apply_log.grid(row=1, column=0, columnspan=4, sticky="w", pady=(GAP_S, 0))
        self._load_settings()

    def _add_setting(self, parent, s, row: int, line: bool = True) -> int:
        """One setting from grid row `row`: a hairline above it (line), its name with the help under it on the left,
        its control and the "changed" mark on the right. A "text" setting puts its box across the whole card under the
        help. Returns the next free row."""
        sid = cfg.setting_id(s)
        if line:
            self._line(parent, row, columns=3)
        row += 1
        text = ttk.Frame(parent, style="Card.TFrame")
        text.grid(row=row, column=0, sticky="nw", padx=(0, GAP_XL), pady=(GAP_XS, GAP_XS))
        ttk.Label(text, text=s.label, style="Card.TLabel").pack(anchor="w")
        ttk.Label(text, text=s.help, style="Card.Muted.TLabel", wraplength=470 if s.kind != "text" else 760,
                  justify="left").pack(anchor="w", pady=(2, 0))
        mark = ttk.Label(parent, text="", style="Warn.TLabel", width=8)
        mark.grid(row=row, column=2, sticky="nw", padx=(GAP_S, 0), pady=(GAP_XS + 3, 0))
        self.changed_marks[sid] = mark
        if s.kind == "text":
            var, box = self._text_box(parent, s)
            box.grid(row=row + 1, column=0, columnspan=3, sticky="we", pady=(GAP_S, GAP_XS))
            self.setting_vars[sid] = var
            return row + 2
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
        widget.grid(row=row, column=1, sticky="nw", pady=(GAP_XS, 0))
        self.setting_vars[sid] = var
        return row + 1

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
        self._line(form, row, columns=3)
        row += 1
        head = ttk.Frame(form, style="Card.TFrame")
        head.grid(row=row, column=0, columnspan=3, sticky="w", pady=(GAP_XS, GAP_XS))
        part = {"items": items, "open": False, "button": ttk.Button(head),
                "note": ttk.Label(head, text="", style="Card.Muted.TLabel")}
        part["button"].configure(command=lambda: self._toggle_advanced(part))
        part["button"].pack(side="left")
        part["note"].pack(side="left", padx=(GAP_M, 0))
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
        """Open the type-to-search picker under a "search" setting's button (voice typing's 100 languages, the read
        aloud voices)."""
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
               title=s.label, anchor=anchor, palette=palette, show_code=s.show_code,
               empty=f"No {s.label.lower()} matches. Esc closes.")

    def _load_settings(self) -> None:
        self.profile = prof.resolve_profile(self.profile["name"])
        usage_log.configure(self.profile)
        values = cfg.current_values(self.profile)
        models = cfg.installed_models(self.profile)
        for box in self.model_boxes:
            box.configure(values=models)
        # only model settings: the context sizes live in the same "models" section of the machine file
        model_ids = {cfg.setting_id(s) for s in cfg.SETTINGS if s.kind == "model"}
        for sid, var in self.setting_vars.items():
            var.set(values[sid])
            if sid in model_ids and values[sid] and values[sid] not in models:
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

    def _apply_settings(self, confirmed: bool = False) -> None:
        edits = self._edits()
        todo = cfg.changed(self.profile, edits)
        if not todo:
            return
        if any(s.effect == "ollama" for s in todo) and not confirmed:
            self._confirm("Restart Ollama?", "These changes restart Ollama. Requests in progress fail, and the next "
                          "request loads its model again (up to a minute or two).", "Restart Ollama and apply",
                          lambda: self._apply_settings(confirmed=True), cancel="Not now", danger=False)
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
