#!/usr/bin/env python3
"""Agent Stack tray app: keeps the stack's services running in the background and shows their status.

It lives in the notification area (on Windows it starts among the hidden icons). Left-click or "Show status" opens a
window with three tabs:
  Overview  each service's health with start/stop and links into the UIs, plus the models loaded in Ollama
  Usage     requests, tokens, speed and cost per model from the gateway traces, with a tokens-per-day chart
  Settings  models, context sizes, tracing and Ollama runtime options; Apply writes machines/<HOST>.yaml,
            rebuilds the generated configs and restarts what the change affects
The icon colour summarises health: green all up, amber some down, red gateway down.

Run it detached with `uv run scripts/stack.py tray`, or inline with `uv run scripts/stack.py tray --foreground`.
Started this way it is not tied to a terminal or Claude Code session, so the services it starts keep running.
"""
from __future__ import annotations

import os
import queue
import sys
import threading
import tkinter as tk
import webbrowser
from datetime import date, datetime, timezone
from pathlib import Path
from tkinter import messagebox, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pystray  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from stacklib import IS_WINDOWS, REPO, ollama, profile as prof, services  # noqa: E402
from stacklib import settings as cfg  # noqa: E402
from stacklib import startup, usage  # noqa: E402

POLL_SECONDS = 10
LABELS = {
    "ollama": "Ollama",
    "phoenix": "Phoenix",
    "litellm": "LiteLLM gateway",
    "orchestrator": "Orchestrator MCP",
    "open_webui": "Open WebUI",
}
ROLES = {
    "ollama": "runs the local models",
    "phoenix": "trace viewer",
    "litellm": "one API for every model",
    "orchestrator": "department delegation for agents",
    "open_webui": "chat in the browser",
}
COLORS = {"ok": "#2e9d57", "warn": "#d99a1e", "bad": "#c94a3d", "idle": "#8a8f98"}  # tray icon fills
FONT = "Segoe UI" if IS_WINDOWS else "TkDefaultFont"

# Window palette (light / dark): neutral surfaces, one blue accent for data, status colours only for state.
THEMES = {
    "light": {
        "page": "#f3f3f1", "card": "#fcfcfb", "ink": "#0b0b0b", "ink2": "#52514e", "muted": "#898781",
        "grid": "#e1e0d9", "border": "#dcdbd4", "accent": "#2a78d6", "accent_ink": "#ffffff", "hover": "#ebeae5",
        "good": "#0ca30c", "warn": "#b07a00", "bad": "#d03b3b", "select": "#dbe8f8",
    },
    "dark": {
        "page": "#111110", "card": "#1a1a19", "ink": "#f0efec", "ink2": "#c3c2b7", "muted": "#898781",
        "grid": "#2c2c2a", "border": "#33332f", "accent": "#3987e5", "accent_ink": "#ffffff", "hover": "#252523",
        "good": "#0ca30c", "warn": "#fab219", "bad": "#e05252", "select": "#1f3a5c",
    },
}
RANGES = [("Today", 1), ("7 days", 7), ("30 days", 30)]


def ui_links(p: dict) -> dict[str, str]:
    ports = p["ports"]
    return {
        "open_webui": f"http://127.0.0.1:{ports['open_webui']}",
        "phoenix": f"http://127.0.0.1:{ports['phoenix']}",
        "litellm": f"http://127.0.0.1:{ports['litellm']}/ui",
    }


def make_icon(color: str) -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((4, 4, 60, 60), fill=color)
    d.polygon([(32, 14), (48, 50), (40, 50), (32, 30), (24, 50), (16, 50)], fill="white")  # stylised "A"
    return img


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


class TrayApp:
    def __init__(self, autostart: bool = True) -> None:
        self.profile = prof.resolve_profile()
        self.managed = [s for s in services.SERVICE_ORDER if s in services.commands(self.profile)]
        self.rows: list[dict] = []
        self.loaded: list[dict] = []
        self.usage_data: dict | None = None
        self.usage_days = 7
        self.usage_group = "alias"
        self.busy = ""
        self.checked_at = ""
        self.ui_queue: queue.Queue = queue.Queue()
        self.stop_event = threading.Event()
        self.root = tk.Tk()
        self.root.withdraw()
        self.window: tk.Toplevel | None = None
        self.refresh_lock = threading.Lock()
        self.icon_color = COLORS["idle"]
        self.icon = pystray.Icon("agent-stack", make_icon(COLORS["idle"]), "Agent Stack: starting", menu=self._menu())
        if autostart:
            self._in_background("Starting services", lambda: services.start(self.profile, self.managed))

    # ---------- state ----------
    def refresh(self) -> None:
        # Refreshes come from the poller and from start/stop threads; pystray's Windows backend frees the old icon
        # handle on every swap, so two concurrent swaps fail with WinError 1402. Serialise, and swap only on change.
        with self.refresh_lock:
            self.rows = services.status(self.profile)
            self.loaded = ollama.ps(f"http://127.0.0.1:{self.profile['ports']['ollama']}")
            self.checked_at = datetime.now().strftime("%H:%M:%S")
            up = {r["service"] for r in self.rows if r["healthy"]}
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
            self.icon.title = f"Agent Stack: {n_up}/{len(wanted)} up" + (f" ({self.busy})" if self.busy else "")
            self.icon.update_menu()
        self.ui_queue.put(self._render_window)
        self.refresh_usage()

    def refresh_usage(self) -> None:
        try:
            self.usage_data = usage.summarize(self.usage_days, self.usage_group)
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

    def _in_background(self, what: str, fn) -> None:
        def run() -> None:
            self.busy = what.lower()
            self.refresh_soon()
            try:
                fn()
                services.wait_healthy(self.profile, self.managed, timeout=180) if what.startswith("Start") else None
            except Exception as e:  # noqa: BLE001
                print(f"[tray] {what} failed: {e}")
            finally:
                self.busy = ""
                self.refresh_soon()

        threading.Thread(target=run, daemon=True).start()

    def refresh_soon(self) -> None:
        threading.Thread(target=self.refresh, daemon=True).start()

    # ---------- actions ----------
    def start_all(self, *_):
        self._in_background("Starting services", lambda: services.start(self.profile, self.managed))

    def stop_all(self, *_):
        self._in_background("Stopping services", lambda: services.stop(self.profile, self.managed))

    def toggle(self, svc: str) -> None:
        healthy = any(r["service"] == svc and r["healthy"] for r in self.rows)
        if healthy:
            self._in_background(f"Stopping {svc}", lambda: services.stop(self.profile, [svc]))
        else:
            self._in_background(f"Starting {svc}", lambda: services.start(self.profile, [svc]))

    def open_url(self, svc: str) -> None:
        webbrowser.open(ui_links(self.profile)[svc])

    def open_path(self, path: Path) -> None:
        os.startfile(str(path)) if os.name == "nt" else webbrowser.open(path.as_uri())

    def open_logs(self, *_):
        self.open_path(Path(self.profile["data_dir"]) / "logs")

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
            row = next((r for r in self.rows if r["service"] == svc), None)
            mark = "● up" if row and row["healthy"] else "○ down"
            return f"{LABELS[svc]}: {mark}"

        return text

    def _menu(self) -> pystray.Menu:
        links = ui_links(prof.resolve_profile())
        return pystray.Menu(
            pystray.MenuItem("Show status", lambda *_: self.ui_queue.put(lambda: self.show_window(0)), default=True),
            pystray.MenuItem("Usage by model", lambda *_: self.ui_queue.put(lambda: self.show_window(1))),
            pystray.MenuItem("Settings", lambda *_: self.ui_queue.put(lambda: self.show_window(2))),
            pystray.Menu.SEPARATOR,
            *[pystray.MenuItem(self._status_text(s), None, enabled=False) for s in ["ollama", *services.SERVICE_ORDER]],
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Open chat (Open WebUI)", lambda *_: webbrowser.open(links["open_webui"])),
            pystray.MenuItem("Open traces (Phoenix)", lambda *_: webbrowser.open(links["phoenix"])),
            pystray.MenuItem("Open gateway admin (LiteLLM)", lambda *_: webbrowser.open(links["litellm"])),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Start all services", self.start_all),
            pystray.MenuItem("Stop all services", self.stop_all),
            pystray.MenuItem("Open logs folder", self.open_logs),
            pystray.MenuItem("Start at login", lambda *_: self._toggle_startup(), checked=lambda _item: startup.is_installed()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit (keep services running)", lambda *_: self.quit(False)),
            pystray.MenuItem("Stop services and quit", lambda *_: self.quit(True)),
        )

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
        s.configure("TButton", background=t["card"], foreground=t["ink"], padding=(10, 4), relief="flat", borderwidth=1)
        s.map("TButton", background=[("disabled", t["page"]), ("active", t["hover"])], foreground=[("disabled", t["muted"])])
        s.configure("Accent.TButton", background=t["accent"], foreground=t["accent_ink"], bordercolor=t["accent"])
        s.map("Accent.TButton", background=[("disabled", t["border"]), ("active", t["accent"])])
        s.configure("Seg.TRadiobutton", background=t["card"], foreground=t["ink2"], padding=(10, 3), indicatorrelief="flat")
        s.layout("Seg.TRadiobutton", [("Radiobutton.padding", {"sticky": "nswe", "children": [("Radiobutton.label", {"sticky": "nswe"})]})])
        s.map("Seg.TRadiobutton", background=[("selected", t["select"]), ("active", t["hover"])], foreground=[("selected", t["ink"])])
        for w in ("TCheckbutton",):
            s.configure(w, background=t["card"], foreground=t["ink"], indicatorbackground=t["card"], indicatorforeground=t["accent"])
            s.map(w, background=[("active", t["card"])], indicatorbackground=[("selected", t["card"])])
        s.configure("Page.TCheckbutton", background=t["page"])
        s.map("Page.TCheckbutton", background=[("active", t["page"])])
        s.configure("TCombobox", fieldbackground=t["card"], background=t["card"], foreground=t["ink"], arrowcolor=t["ink2"], padding=3)
        s.map("TCombobox", fieldbackground=[("readonly", t["card"])], foreground=[("readonly", t["ink"])],
              selectbackground=[("readonly", t["card"])], selectforeground=[("readonly", t["ink"])])
        self.root.option_add("*TCombobox*Listbox.background", t["card"])
        self.root.option_add("*TCombobox*Listbox.foreground", t["ink"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", t["select"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", t["ink"])
        s.configure("TNotebook", background=t["page"], borderwidth=0, tabmargins=(0, 0, 0, 0))
        s.configure("TNotebook.Tab", background=t["page"], foreground=t["ink2"], padding=(16, 7), borderwidth=0, font=(FONT, 10))
        s.map("TNotebook.Tab", background=[("selected", t["card"])], foreground=[("selected", t["ink"])],
              lightcolor=[("selected", t["card"])], bordercolor=[("selected", t["border"])], expand=[("selected", (0, 0, 0, 0))])
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

    def _build_window(self) -> None:
        self._style()
        t = self.t
        w = tk.Toplevel(self.root, bg=t["page"])
        w.title("Agent Stack")
        w.geometry("940x720")
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
        self.tabs.bind("<<NotebookTabChanged>>", lambda _e: self._render_usage())
        self._build_overview(ttk.Frame(self.tabs, padding=(0, 12, 0, 0)))
        self._build_usage(ttk.Frame(self.tabs, padding=(0, 12, 0, 0)))
        self._build_settings(ttk.Frame(self.tabs, padding=(0, 12, 0, 0)))

    # ---------- Overview tab ----------
    def _build_overview(self, tab: ttk.Frame) -> None:
        self.tabs.add(tab, text="Overview")
        tab.columnconfigure(0, weight=1)
        card = self._card(tab, "Services", row=0, column=0)
        card.columnconfigure(1, weight=1)
        self.row_widgets: dict[str, tuple] = {}
        links = ui_links(self.profile)
        for i, svc in enumerate(["ollama", *services.SERVICE_ORDER], start=1):
            dot = tk.Label(card, text="●", font=(FONT, 12), bg=self.t["card"])
            dot.grid(row=i, column=0, padx=(0, 10), pady=5)
            names = ttk.Frame(card, style="Card.TFrame")
            names.grid(row=i, column=1, sticky="w")
            ttk.Label(names, text=LABELS[svc], style="Card.TLabel", font=(FONT, 10, "bold")).pack(anchor="w")
            ttk.Label(names, text=f"{ROLES[svc]}  ·  port {self.profile['ports'][svc]}", style="Card.Muted.TLabel").pack(anchor="w")
            state = ttk.Label(card, text="", style="Card.Sub.TLabel", width=16)
            state.grid(row=i, column=2, sticky="w", padx=8)
            buttons = ttk.Frame(card, style="Card.TFrame")
            buttons.grid(row=i, column=3, sticky="e")
            if svc in links:
                ttk.Button(buttons, text="Open", width=7, command=lambda s=svc: self.open_url(s)).pack(side="left", padx=2)
            toggle = ttk.Button(buttons, text="Stop", width=7, command=lambda s=svc: self.toggle(s))
            if svc != "ollama":
                toggle.pack(side="left", padx=2)
            self.row_widgets[svc] = (dot, state, toggle)

        models = self._card(tab, "Loaded in Ollama", row=1, column=0, pady=(12, 0))
        models.columnconfigure(0, weight=1)
        self.loaded_frame = ttk.Frame(models, style="Card.TFrame")
        self.loaded_frame.grid(row=1, column=0, sticky="we")

        bar = ttk.Frame(tab, padding=(0, 12, 0, 0))
        bar.grid(row=2, column=0, sticky="we")
        ttk.Button(bar, text="Open chat", style="Accent.TButton", command=lambda: self.open_url("open_webui")).pack(side="left")
        self.start_btn = ttk.Button(bar, text="Start all", command=self.start_all)
        self.start_btn.pack(side="left", padx=(8, 4))
        self.stop_btn = ttk.Button(bar, text="Stop all", command=self.stop_all)
        self.stop_btn.pack(side="left")
        ttk.Button(bar, text="Logs", command=self.open_logs).pack(side="left", padx=4)
        self.startup_var = tk.BooleanVar(value=startup.is_installed())
        ttk.Checkbutton(bar, text="Start at login", style="Page.TCheckbutton", variable=self.startup_var,
                        command=self._toggle_startup).pack(side="right")

    def _render_window(self) -> None:
        if self.window is None or not self.window.winfo_exists():
            return
        t = self.t
        rows = {r["service"]: r for r in self.rows}
        up = 0
        for svc, (dot, state, toggle) in self.row_widgets.items():
            healthy = bool(rows.get(svc, {}).get("healthy"))
            enabled = svc == "ollama" or svc in self.managed
            up += healthy and enabled
            pid = rows.get(svc, {}).get("pid")
            if healthy:
                dot.configure(fg=t["good"])
                state.configure(text=f"Running{f'  (pid {pid})' if pid else ''}")
            elif enabled:
                dot.configure(fg=t["bad"])
                state.configure(text="Stopped")
            else:
                dot.configure(fg=t["muted"])
                state.configure(text="Off in settings")
            toggle.configure(text="Stop" if healthy else "Start",
                             state="disabled" if self.busy or not (enabled or healthy) else "normal")
        total = sum(1 for s in self.row_widgets if s == "ollama" or s in self.managed)
        self.pill_dot.configure(fg=t["good"] if up == total else (t["warn"] if up else t["bad"]))
        busy = f"  ·  {self.busy}..." if self.busy else ""
        self.pill_text.configure(text=f"{up}/{total} running  ·  checked {self.checked_at or '...'}{busy}")
        m = self.profile["models"]
        cloud = "cloud tiers on" if self.profile["cloud_enabled"] else "local only"
        self.head_sub.configure(text=f"{self.profile['name']}  ·  primary {m.get('primary')} @ {compact(m.get('primary_num_ctx', 0))} ctx  ·  {cloud}")
        for b in (self.start_btn, self.stop_btn):
            b.configure(state="disabled" if self.busy else "normal")
        self.startup_var.set(startup.is_installed())
        self._render_loaded()

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
        for label, val in (("Gateway alias", "alias"), ("Served model", "served")):
            ttk.Radiobutton(tools, text=label, value=val, variable=self.group_var, style="Seg.TRadiobutton",
                            command=self._usage_changed).pack(side="left")
        self.cost_note = ttk.Label(tools, text="", style="Card.Muted.TLabel")
        self.cost_note.pack(side="right")

        tiles = ttk.Frame(tab)
        tiles.grid(row=1, column=0, sticky="we", pady=(12, 0))
        self.tile_values: dict[str, ttk.Label] = {}
        for i, (key, label) in enumerate((("requests", "Requests"), ("prompt_tokens", "Input tokens"),
                                          ("completion_tokens", "Output tokens"), ("errors", "Errors"), ("cost", "API cost"))):
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
        cols = [("model", "Model", 160, "w"), ("requests", "Requests", 80, "e"), ("errors", "Errors", 60, "e"),
                ("prompt_tokens", "Input tok", 90, "e"), ("completion_tokens", "Output tok", 90, "e"),
                ("avg_latency_ms", "Avg latency", 90, "e"), ("tok_per_s", "Output tok/s", 90, "e"),
                ("cost", "Cost", 70, "e"), ("last", "Last used", 80, "e")]
        self.usage_sort = ("total", True)
        self.tree = ttk.Treeview(table, columns=[c[0] for c in cols], show="headings", selectmode="browse", height=6)
        for key, label, width, anchor in cols:
            self.tree.heading(key, text=label, anchor=anchor, command=lambda k=key: self._sort_usage(k))
            self.tree.column(key, width=width, anchor=anchor, stretch=key == "model")
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._draw_chart())
        self.tree.tag_configure("err", foreground=self.t["bad"])
        self.usage_empty = ttk.Label(table, text="", style="Card.Muted.TLabel", wraplength=640, justify="left")

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
        for key, label in self.tile_values.items():
            label.configure(text=f"${tot[key]:.2f}" if key == "cost" else compact(tot[key]) if key.endswith("tokens") else f"{tot[key]:,}")
        self.tile_values["errors"].configure(foreground=self.t["bad"] if tot["errors"] else self.t["ink"])
        self.cost_note.configure(text="Local models cost $0; cost is cloud API spend.")
        selected = self.tree.selection()
        keep = selected[0] if selected else None
        self.tree.delete(*self.tree.get_children())
        key, rev = self.usage_sort
        rows = sorted(data["models"], key=lambda m: (m["prompt_tokens"] + m["completion_tokens"]) if key == "total"
                      else (m[key] if m[key] is not None else -1), reverse=rev)
        for m in rows:
            self.tree.insert("", "end", iid=m["model"], tags=("err",) if m["errors"] and m["errors"] == m["requests"] else (), values=(
                m["model"], f"{m['requests']:,}", m["errors"] or "", compact(m["prompt_tokens"]), compact(m["completion_tokens"]),
                f"{m['avg_latency_ms'] / 1000:.1f} s", f"{m['tok_per_s']:.0f}" if m["tok_per_s"] else "-",
                f"${m['cost']:.4f}" if m["cost"] else "-", usage.ago(m["last"])))
        if keep and self.tree.exists(keep):
            self.tree.selection_set(keep)
        if rows:
            self.usage_empty.grid_forget()
        else:
            on = self.profile["observability"].get("jsonl_traces", True)
            self.usage_empty.configure(text="No gateway requests in this period." + (
                "" if on else " Usage traces are off: turn on 'Write usage traces' in Settings."))
            self.usage_empty.grid(row=1, column=0, sticky="w", pady=(8, 0))
        self._draw_chart()

    def _draw_chart(self) -> None:
        if self.usage_data is None or not hasattr(self, "canvas"):
            return
        t, c = self.t, self.canvas
        c.delete("all")
        sel = self.tree.selection()
        days = self.usage_data["days"]
        if sel:
            model = next((m for m in self.usage_data["models"] if m["model"] == sel[0]), None)
            values = model["daily"] if model else [0] * len(days)
            self.chart_title.configure(text=f"Tokens per day  ·  {sel[0]}")
        else:
            values = self.usage_data["totals"]["daily"]
            self.chart_title.configure(text="Tokens per day  ·  all models (select a row to filter)")
        w, h = max(c.winfo_width(), 200), max(c.winfo_height(), 100)
        left, right, top, bottom = 48, 8, 8, 22
        top_val = max(values) if any(values) else 1
        plot_h, plot_w = h - top - bottom, w - left - right
        for frac in (0, 0.5, 1):  # recessive hairline grid with compact labels
            y = top + plot_h * (1 - frac)
            c.create_line(left, y, w - right, y, fill=t["grid"] if frac else t["border"])
            c.create_text(left - 8, y, text=compact(top_val * frac), anchor="e", fill=t["muted"], font=(FONT, 8))
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
        text = f"{datetime.fromisoformat(d).strftime('%a %b %d')}: {v:,} tokens"
        tx = min(max(e.x + 12, 4), c.winfo_width() - 170)
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
        scroll = tk.Canvas(outer, bg=self.t["card"], highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient="vertical", command=scroll.yview)
        scroll.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        scroll.pack(side="left", fill="both", expand=True)
        form = ttk.Frame(scroll, style="Card.TFrame", padding=(18, 14))
        win = scroll.create_window(0, 0, window=form, anchor="nw")
        form.bind("<Configure>", lambda _e: scroll.configure(scrollregion=scroll.bbox("all")))
        scroll.bind("<Configure>", lambda e: scroll.itemconfigure(win, width=e.width))
        form.bind_all("<MouseWheel>", lambda e: scroll.yview_scroll(int(-e.delta / 120), "units")
                      if self.tabs.index("current") == 2 else None, add="+")
        form.columnconfigure(1, weight=1)
        self.form = form

        groups = [("Models", "models"), ("Tracing and services", ("observability", "services")), ("Ollama runtime", "ollama_env")]
        self.setting_vars: dict[str, tk.Variable] = {}
        self.model_boxes: list[ttk.Combobox] = []
        self.changed_marks: dict[str, ttk.Label] = {}
        row = 0
        for title, sections in groups:
            ttk.Label(form, text=title, style="Card.Title.TLabel").grid(row=row, column=0, columnspan=3, sticky="w", pady=(8 if row else 0, 4))
            row += 1
            if title == "Ollama runtime":
                ttk.Label(form, text="Applying any of these restarts Ollama, which interrupts requests in progress.",
                          style="Card.Muted.TLabel").grid(row=row, column=0, columnspan=3, sticky="w", pady=(0, 6))
                row += 1
            for s in cfg.SETTINGS:
                if s.section not in (sections if isinstance(sections, tuple) else (sections,)):
                    continue
                sid = cfg.setting_id(s)
                ttk.Label(form, text=s.label, style="Card.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 24), pady=(6, 0))
                if s.kind == "bool":
                    var: tk.Variable = tk.BooleanVar()
                    widget = ttk.Checkbutton(form, variable=var, text="On", command=self._settings_dirty)
                else:
                    var = tk.StringVar()
                    widget = ttk.Combobox(form, textvariable=var, values=s.choices, state="readonly", width=30)
                    widget.bind("<<ComboboxSelected>>", lambda _e: self._settings_dirty())
                    if s.kind == "model":
                        self.model_boxes.append(widget)
                widget.grid(row=row, column=1, sticky="w", pady=(6, 0))
                mark = ttk.Label(form, text="", style="Warn.TLabel")
                mark.grid(row=row, column=2, sticky="e", pady=(6, 0))
                self.changed_marks[sid] = mark
                self.setting_vars[sid] = var
                ttk.Label(form, text=s.help, style="Card.Muted.TLabel", wraplength=560, justify="left").grid(
                    row=row + 1, column=0, columnspan=2, sticky="w", pady=(0, 4))
                row += 2
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

    def _load_settings(self) -> None:
        self.profile = prof.resolve_profile(self.profile["name"])
        values = cfg.current_values(self.profile)
        models = cfg.installed_models(self.profile)
        for box in self.model_boxes:
            box.configure(values=models)
        for sid, var in self.setting_vars.items():
            var.set(values[sid])
            if sid.startswith("models.") and isinstance(var, tk.StringVar) and values[sid] and values[sid] not in models:
                for box in self.model_boxes:  # keep the configured model selectable even when it is not pulled
                    box.configure(values=sorted({*box.cget("values"), values[sid]}))
        key = self.profile["cloud_key_env"]
        self.cloud_label.configure(text=(
            f"Cloud tiers: on ({key} is set). Complex requests may leave this machine." if self.profile["cloud_enabled"] else
            f"Cloud tiers: off. No {key} in .env, so every tier is served locally. This stays a .env decision on purpose "
            "(private first; see memory/state.md open item 4)."))
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
        if todo:
            effects = sorted({cfg.EFFECT_TEXT[s.effect] for s in todo})
            self.pending_label.configure(text=f"{len(todo)} unsaved change{'s' if len(todo) > 1 else ''}. Apply will: " + "; ".join(effects) + ".")
        else:
            self.pending_label.configure(text=f"Saved in machines/{self.profile['name']}.yaml. Defaults come from machines/_defaults.yaml.")
        state = "normal" if todo and not self.busy else "disabled"
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
            self.busy = "applying settings"
            self.ui_queue.put(self._settings_dirty)
            self.refresh_soon()
            try:
                new = cfg.apply(self.profile, edits, log=log)
                self.profile = new
                self.managed = [s for s in services.SERVICE_ORDER if s in services.commands(new)]
                log("Done.")
            except Exception as e:  # noqa: BLE001 - report every failure in the window
                log(f"Failed: {e}")
            finally:
                self.busy = ""
                self.ui_queue.put(self._load_settings)
                self.refresh_soon()

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
        if not self.stop_event.is_set():
            self.root.after(200, self._drain_ui_queue)

    def run(self) -> None:
        threading.Thread(target=self._poll, daemon=True).start()
        self.icon.run_detached()
        self.root.after(200, self._drain_ui_queue)
        if "--show" in sys.argv:
            self.ui_queue.put(lambda: self.show_window(0))
        self.root.mainloop()


def main() -> int:
    log_dir = REPO / ".run" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    if sys.stdout is None or not sys.stdout.isatty():  # pythonw has no console: keep a log instead
        log = open(log_dir / "tray.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = log
    print(f"[tray] {datetime.now().isoformat(timespec='seconds')} starting pid {os.getpid()}")
    if not startup.claim_single_instance():
        print("[tray] another tray instance is running; exiting")
        return 0
    TrayApp(autostart="--no-autostart" not in sys.argv).run()
    print("[tray] exited")
    return 0


if __name__ == "__main__":
    sys.exit(main())
