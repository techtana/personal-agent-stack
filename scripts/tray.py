#!/usr/bin/env python3
"""Agent Stack tray app: keeps the stack's services running in the background and shows their status.

It lives in the notification area (on Windows it starts among the hidden icons). Left-click or "Show status" opens a
small window with each service's health, links into the UIs (Open WebUI, Phoenix, LiteLLM admin) and start/stop
controls. The icon colour summarises health: green all up, amber some down, red gateway down.

Run it detached with `uv run scripts/stack.py tray`, or inline with `uv run scripts/stack.py tray --foreground`.
Started this way it is not tied to a terminal or Claude Code session, so the services it starts keep running.
"""
from __future__ import annotations

import os
import queue
import sys
import threading
import time
import tkinter as tk
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import ttk

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pystray  # noqa: E402
from PIL import Image, ImageDraw, ImageTk  # noqa: E402

from stacklib import REPO, metrics, process_metrics, profile as prof, services  # noqa: E402
from stacklib import startup  # noqa: E402

POLL_SECONDS = 10
LABELS = {
    "ollama": "Ollama (models)",
    "phoenix": "Phoenix (traces)",
    "litellm": "LiteLLM gateway",
    "orchestrator": "Orchestrator MCP",
    "open_webui": "Open WebUI (chat)",
}
COLORS = {"ok": "#2e9d57", "warn": "#d99a1e", "bad": "#c94a3d", "idle": "#8a8f98"}


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


class TrayApp:
    def __init__(self, autostart: bool = True) -> None:
        self.profile = prof.resolve_profile()
        self.managed = [s for s in services.SERVICE_ORDER if s in services.commands(self.profile)]
        self.rows: list[dict] = []
        self.metrics_period = "24 hours"
        self.metric_rows: list[dict] = []
        self.process_sampler = process_metrics.ProcessSampler()
        self.process_rows: list[dict] = []
        self.busy = ""
        self.checked_at = ""
        self.ui_queue: queue.Queue = queue.Queue()
        self.stop_event = threading.Event()
        self.root = tk.Tk()
        self.root.withdraw()
        self.style = ttk.Style(self.root)
        self._configure_ui_styles()
        self.window: tk.Toplevel | None = None
        self.window_icon: ImageTk.PhotoImage | None = None
        self.window_icon_color: str | None = None
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
            self.metric_rows = metrics.summarize(REPO / "traces" / "litellm", self.metrics_period)
            self.process_rows = self.process_sampler.sample()
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
        state = next((r["state"] for r in self.rows if r["service"] == svc), "stopped")
        if state != "stopped":
            self._in_background(f"Stopping {svc}", lambda: services.stop(self.profile, [svc]))
        else:
            self._in_background(f"Starting {svc}", lambda: services.start(self.profile, [svc]))

    def open_url(self, svc: str) -> None:
        webbrowser.open(ui_links(self.profile)[svc])

    def open_logs(self, *_):
        os.startfile(str(Path(self.profile["data_dir"]) / "logs")) if os.name == "nt" else webbrowser.open((Path(self.profile["data_dir"]) / "logs").as_uri())

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
            pystray.MenuItem("Show status", lambda *_: self.ui_queue.put(self.show_window), default=True),
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

    def _metrics_period_changed(self, _event=None) -> None:
        self.metrics_period = self.metrics_period_var.get()
        self.refresh_soon()

    # ---------- status window ----------
    def show_window(self) -> None:
        if self.window is None or not self.window.winfo_exists():
            self._build_window()
        self._render_window()
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()

    def _set_window_icon(self) -> None:
        if self.window is None:
            return
        self.window_icon = ImageTk.PhotoImage(make_icon(self.icon_color), master=self.window)
        self.window.iconphoto(True, self.window_icon)
        self.window_icon_color = self.icon_color

    def _configure_ui_styles(self) -> None:
        if "clam" in self.style.theme_names():
            self.style.theme_use("clam")
        self.style.configure(".", font=("Segoe UI", 9), foreground="#243044")
        self.style.configure("App.TFrame", background="#f2f5f9")
        self.style.configure("Card.TFrame", background="#ffffff")
        self.style.configure("TLabel", background="#f2f5f9", foreground="#243044")
        self.style.configure("Card.TLabel", background="#ffffff", foreground="#243044")
        self.style.configure("Title.TLabel", background="#f2f5f9", foreground="#17243a", font=("Segoe UI", 20, "bold"))
        self.style.configure("Subtitle.TLabel", background="#f2f5f9", foreground="#66758a", font=("Segoe UI", 9))
        self.style.configure("Section.TLabel", background="#ffffff", foreground="#17243a", font=("Segoe UI", 11, "bold"))
        self.style.configure("Muted.Card.TLabel", background="#ffffff", foreground="#718096", font=("Segoe UI", 9))
        for name, background, foreground in (
            ("Ok", "#e6f4ec", "#227447"),
            ("Warn", "#fff3d9", "#986610"),
            ("Bad", "#fbe9e7", "#a33b32"),
            ("Idle", "#edf1f6", "#66758a"),
        ):
            self.style.configure(
                f"{name}.Summary.TLabel",
                background=background,
                foreground=foreground,
                padding=(10, 6),
                font=("Segoe UI", 9, "bold"),
            )
        for name, background, foreground in (
            ("Running", "#e6f4ec", "#227447"),
            ("Starting", "#fff3d9", "#986610"),
            ("Stopped", "#f0f2f5", "#66758a"),
            ("Error", "#fbe9e7", "#a33b32"),
        ):
            self.style.configure(
                f"{name}.ServiceState.TLabel",
                background=background,
                foreground=foreground,
                padding=(8, 3),
            )
        self.style.configure("TButton", padding=(10, 6), background="#e8edf4", borderwidth=0)
        self.style.map("TButton", background=[("pressed", "#d5deea"), ("active", "#dfe7f1")])
        self.style.configure("Primary.TButton", padding=(12, 7), background="#2864c5", foreground="#ffffff", font=("Segoe UI", 9, "bold"))
        self.style.map("Primary.TButton", background=[("pressed", "#1d4f9e"), ("active", "#3474d4")])
        self.style.configure("TNotebook", background="#f2f5f9", borderwidth=0)
        self.style.configure("TNotebook.Tab", padding=(16, 9), background="#e8edf4", foreground="#66758a")
        self.style.map(
            "TNotebook.Tab",
            background=[("selected", "#ffffff"), ("active", "#f8fafc")],
            foreground=[("selected", "#2864c5")],
        )
        self.style.configure(
            "Treeview",
            background="#ffffff",
            fieldbackground="#ffffff",
            foreground="#243044",
            rowheight=28,
            borderwidth=0,
            font=("Segoe UI", 9),
        )
        self.style.configure(
            "Treeview.Heading",
            background="#edf1f6",
            foreground="#56657a",
            padding=(7, 8),
            font=("Segoe UI", 9, "bold"),
            relief="flat",
        )
        self.style.map("Treeview", background=[("selected", "#dce9fb")], foreground=[("selected", "#17243a")])

    def _build_window(self) -> None:
        w = tk.Toplevel(self.root)
        w.title("Agent Stack")
        w.geometry("1120x730")
        w.minsize(900, 620)
        w.configure(background="#f2f5f9")
        w.protocol("WM_DELETE_WINDOW", w.withdraw)  # closing hides it; the tray keeps running
        w.columnconfigure(0, weight=1)
        w.rowconfigure(0, weight=1)
        frame = ttk.Frame(w, style="App.TFrame", padding=22)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        header = ttk.Frame(frame, style="App.TFrame")
        header.grid(row=0, column=0, sticky="we", pady=(0, 18))
        ttk.Label(header, text="Agent Stack", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Local-first AI services, usage, and system health",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))
        self.summary = ttk.Label(header, text="", style="Ok.Summary.TLabel", anchor="e")
        self.summary.grid(row=0, column=1, rowspan=2, sticky="e")
        header.columnconfigure(0, weight=1)

        notebook = ttk.Notebook(frame)
        notebook.grid(row=1, column=0, sticky="nsew")
        overview = ttk.Frame(notebook, style="App.TFrame", padding=(0, 16, 0, 0))
        usage_page = ttk.Frame(notebook, style="App.TFrame", padding=(0, 16, 0, 0))
        resources_page = ttk.Frame(notebook, style="App.TFrame", padding=(0, 16, 0, 0))
        notebook.add(overview, text="Services")
        notebook.add(usage_page, text="Usage")
        notebook.add(resources_page, text="Resources")

        services_card = ttk.Frame(overview, style="Card.TFrame", padding=18)
        services_card.grid(row=0, column=0, sticky="new")
        overview.columnconfigure(0, weight=1)
        ttk.Label(services_card, text="Services", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            services_card,
            text="Monitor and control the components in your local agent stack.",
            style="Muted.Card.TLabel",
        ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(3, 12))
        self.row_widgets: dict[str, tuple] = {}
        links = ui_links(self.profile)
        for i, svc in enumerate(["ollama", *services.SERVICE_ORDER], start=2):
            row = ttk.Frame(services_card, style="Card.TFrame")
            row.grid(row=i, column=0, columnspan=4, sticky="we", pady=4)
            services_card.columnconfigure(0, weight=1)
            dot = tk.Label(row, text="●", font=("Segoe UI", 11), bg="#ffffff", fg=COLORS["idle"])
            dot.grid(row=0, column=0, padx=(2, 10))
            ttk.Label(row, text=LABELS[svc], style="Card.TLabel", width=24).grid(row=0, column=1, sticky="w")
            state = ttk.Label(row, text="", width=12, anchor="center")
            state.grid(row=0, column=2, sticky="w", padx=(10, 0))
            buttons = ttk.Frame(row, style="Card.TFrame")
            buttons.grid(row=0, column=3, sticky="e")
            if svc in links:
                ttk.Button(buttons, text="Open", width=7, command=lambda s=svc: self.open_url(s)).pack(side="left", padx=2)
            toggle = None
            if svc in self.managed:
                toggle = ttk.Button(buttons, text="Stop", width=7, command=lambda s=svc: self.toggle(s))
                toggle.pack(side="left", padx=2)
            self.row_widgets[svc] = (dot, state, toggle)
            row.columnconfigure(1, weight=1)

        actions = ttk.Frame(overview, style="App.TFrame")
        actions.grid(row=1, column=0, sticky="we", pady=(14, 0))
        ttk.Button(actions, text="Start all", style="Primary.TButton", command=self.start_all).pack(side="left")
        ttk.Button(actions, text="Stop all", command=self.stop_all).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Open chat", command=lambda: self.open_url("open_webui")).pack(side="left", padx=(18, 0))
        ttk.Button(actions, text="Logs", command=self.open_logs).pack(side="left", padx=8)
        self.startup_var = tk.BooleanVar(value=startup.is_installed())
        ttk.Checkbutton(
            actions,
            text="Start at login",
            variable=self.startup_var,
            command=self._toggle_startup,
        ).pack(side="right")

        usage_card = ttk.Frame(usage_page, style="Card.TFrame", padding=18)
        usage_card.grid(row=0, column=0, sticky="nsew")
        usage_page.columnconfigure(0, weight=1)
        usage_page.rowconfigure(0, weight=1)
        metrics_header = ttk.Frame(usage_card, style="Card.TFrame")
        metrics_header.grid(row=0, column=0, sticky="we")
        ttk.Label(metrics_header, text="Request usage & latency", style="Section.TLabel").pack(side="left")
        self.metrics_period_var = tk.StringVar(value=self.metrics_period)
        period_box = ttk.Combobox(
            metrics_header,
            textvariable=self.metrics_period_var,
            values=list(metrics.PERIODS),
            state="readonly",
            width=12,
        )
        period_box.pack(side="right")
        period_box.bind("<<ComboboxSelected>>", self._metrics_period_changed)
        ttk.Label(
            usage_card,
            text="Gateway calls only. Local model phase timings are shown when available.",
            style="Muted.Card.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 10))
        columns = ("process", "model", "requests", "input_tokens", "output_tokens", "total_tokens",
                   "load", "input", "inference", "model_total", "request", "cost")
        self.metrics_tree = ttk.Treeview(usage_card, columns=columns, show="headings", height=14)
        headings = {
            "process": ("Process", 130),
            "model": ("Model", 190),
            "requests": ("Requests", 65),
            "input_tokens": ("Input tokens", 85),
            "output_tokens": ("Output tokens", 90),
            "total_tokens": ("Total tokens", 85),
            "load": ("Avg load", 75),
            "input": ("Avg input", 75),
            "inference": ("Avg inference", 95),
            "model_total": ("Avg model total", 95),
            "request": ("Avg request", 85),
            "cost": ("Cost", 85),
        }
        for column, (title, width) in headings.items():
            self.metrics_tree.heading(column, text=title)
            self.metrics_tree.column(column, width=width, minwidth=55, anchor="w" if column in ("process", "model") else "e")
        metrics_scroll = ttk.Scrollbar(usage_card, orient="vertical", command=self.metrics_tree.yview)
        metrics_xscroll = ttk.Scrollbar(usage_card, orient="horizontal", command=self.metrics_tree.xview)
        self.metrics_tree.configure(yscrollcommand=metrics_scroll.set, xscrollcommand=metrics_xscroll.set)
        self.metrics_tree.grid(row=2, column=0, sticky="nsew")
        metrics_scroll.grid(row=2, column=1, sticky="ns")
        metrics_xscroll.grid(row=3, column=0, sticky="we")
        usage_card.columnconfigure(0, weight=1)
        usage_card.rowconfigure(2, weight=1)

        resources_card = ttk.Frame(resources_page, style="Card.TFrame", padding=18)
        resources_card.grid(row=0, column=0, sticky="nsew")
        resources_page.columnconfigure(0, weight=1)
        resources_page.rowconfigure(0, weight=1)
        ttk.Label(resources_card, text="Live process resources", style="Section.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            resources_card,
            text="CPU is measured between refreshes; GPU metrics are reported by the driver.",
            style="Muted.Card.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 10))
        process_columns = ("name", "pid", "cpu", "memory", "gpu", "gpu_memory")
        self.process_tree = ttk.Treeview(resources_card, columns=process_columns, show="headings", height=16)
        process_headings = {
            "name": ("Process", 260, "w"),
            "pid": ("PID", 80, "e"),
            "cpu": ("CPU %", 90, "e"),
            "memory": ("RAM MB", 100, "e"),
            "gpu": ("GPU engine %", 120, "e"),
            "gpu_memory": ("GPU dedicated MB", 150, "e"),
        }
        for column, (title, width, anchor) in process_headings.items():
            self.process_tree.heading(column, text=title)
            self.process_tree.column(column, width=width, minwidth=60, anchor=anchor)
        process_scroll = ttk.Scrollbar(resources_card, orient="vertical", command=self.process_tree.yview)
        process_xscroll = ttk.Scrollbar(resources_card, orient="horizontal", command=self.process_tree.xview)
        self.process_tree.configure(yscrollcommand=process_scroll.set, xscrollcommand=process_xscroll.set)
        self.process_tree.grid(row=2, column=0, sticky="nsew")
        process_scroll.grid(row=2, column=1, sticky="ns")
        process_xscroll.grid(row=3, column=0, sticky="we")
        resources_card.columnconfigure(0, weight=1)
        resources_card.rowconfigure(2, weight=1)
        self.window = w
        self._set_window_icon()

    def _render_window(self) -> None:
        if self.window is None or not self.window.winfo_exists():
            return
        if self.window_icon_color != self.icon_color:
            self._set_window_icon()
        rows = {r["service"]: r for r in self.rows}
        up = 0
        for svc, (dot, state, toggle) in self.row_widgets.items():
            svc_state = rows.get(svc, {}).get("state", "stopped")
            up += svc_state == "running"
            dot.configure(fg=COLORS["ok"] if svc_state == "running" else COLORS["warn"] if svc_state == "starting" else COLORS["bad"])
            state_style = {
                "running": "Running.ServiceState.TLabel",
                "starting": "Starting.ServiceState.TLabel",
                "stopped": "Stopped.ServiceState.TLabel",
            }.get(svc_state, "Error.ServiceState.TLabel")
            state.configure(text=svc_state, style=state_style)
            if toggle is not None:
                toggle.configure(text="Start" if svc_state == "stopped" else "Stop", state="disabled" if self.busy else "normal")
        busy = f"  {self.busy}..." if self.busy else ""
        self.summary.configure(text=f"{up}/{len(self.row_widgets)} running, checked {self.checked_at}{busy}")
        summary_style = {
            COLORS["ok"]: "Ok.Summary.TLabel",
            COLORS["warn"]: "Warn.Summary.TLabel",
            COLORS["bad"]: "Bad.Summary.TLabel",
            COLORS["idle"]: "Idle.Summary.TLabel",
        }.get(self.icon_color, "Idle.Summary.TLabel")
        self.summary.configure(style=summary_style)
        self.startup_var.set(startup.is_installed())
        for item in self.metrics_tree.get_children():
            self.metrics_tree.delete(item)
        for row in self.metric_rows:
            process = row["process"]
            origin = "Local" if process == "ollama" else "Cloud"
            self.metrics_tree.insert(
                "",
                "end",
                values=(
                    f"{origin} / {process}",
                    row["model"],
                    row["requests"],
                    row["prompt_tokens"],
                    row["completion_tokens"],
                    row["prompt_tokens"] + row["completion_tokens"],
                    self._format_ms(row["avg_model_load_ms"]),
                    self._format_ms(row["avg_input_ms"]),
                    self._format_ms(row["avg_inference_ms"]),
                    self._format_ms(row["avg_model_total_ms"]),
                    self._format_ms(row["avg_latency_ms"]),
                    f"${row['cost_usd']:.4f}" if origin == "Cloud" else "-",
                ),
            )
        if not self.metric_rows:
            self.metrics_tree.insert("", "end", values=("No recorded calls", "", "", "", "", "", "", "", "", "", "", ""))
        for item in self.process_tree.get_children():
            self.process_tree.delete(item)
        for row in self.process_rows:
            self.process_tree.insert(
                "",
                "end",
                values=(
                    row["name"],
                    row["pid"],
                    self._format_percent(row["cpu_percent"]),
                    f"{row['memory_mb']:.1f}",
                    self._format_percent(row["gpu_percent"]),
                    self._format_memory(row["gpu_memory_mb"]),
                ),
            )

    @staticmethod
    def _format_ms(value: float | None) -> str:
        if value is None:
            return "-"
        return f"{value / 1000:.2f} s" if value >= 1000 else f"{value:.0f} ms"

    @staticmethod
    def _format_percent(value: float | None) -> str:
        return f"{value:.1f}" if value is not None else "-"

    @staticmethod
    def _format_memory(value: float | None) -> str:
        return f"{value:.1f}" if value is not None else "-"

    def _drain_ui_queue(self) -> None:
        try:
            while True:
                self.ui_queue.get_nowait()()
        except queue.Empty:
            pass
        if not self.stop_event.is_set():
            self.root.after(200, self._drain_ui_queue)

    def run(self) -> None:
        threading.Thread(target=self._poll, daemon=True).start()
        self.icon.run_detached()
        self.root.after(200, self._drain_ui_queue)
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
