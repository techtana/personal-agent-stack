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
from PIL import Image, ImageDraw  # noqa: E402

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

    def _build_window(self) -> None:
        w = tk.Toplevel(self.root)
        w.title("Agent Stack")
        w.resizable(True, True)
        w.protocol("WM_DELETE_WINDOW", w.withdraw)  # closing hides it; the tray keeps running
        frame = ttk.Frame(w, padding=14)
        frame.grid()
        ttk.Label(frame, text="Agent Stack", font=("Segoe UI", 13, "bold")).grid(row=0, column=0, columnspan=4, sticky="w")
        self.summary = ttk.Label(frame, text="")
        self.summary.grid(row=1, column=0, columnspan=4, sticky="w", pady=(0, 10))
        self.row_widgets: dict[str, tuple] = {}
        links = ui_links(self.profile)
        for i, svc in enumerate(["ollama", *services.SERVICE_ORDER], start=2):
            dot = tk.Label(frame, text="●", font=("Segoe UI", 12))
            dot.grid(row=i, column=0, padx=(0, 6))
            ttk.Label(frame, text=LABELS[svc], width=20).grid(row=i, column=1, sticky="w")
            state = ttk.Label(frame, text="", width=12)
            state.grid(row=i, column=2, sticky="w")
            buttons = ttk.Frame(frame)
            buttons.grid(row=i, column=3, sticky="e")
            if svc in links:
                ttk.Button(buttons, text="Open", width=7, command=lambda s=svc: self.open_url(s)).pack(side="left", padx=2)
            toggle = None
            if svc in self.managed:
                toggle = ttk.Button(buttons, text="Stop", width=7, command=lambda s=svc: self.toggle(s))
                toggle.pack(side="left", padx=2)
            self.row_widgets[svc] = (dot, state, toggle)

        ttk.Separator(frame, orient="horizontal").grid(row=8, column=0, columnspan=4, sticky="we", pady=(12, 8))
        metrics_header = ttk.Frame(frame)
        metrics_header.grid(row=9, column=0, columnspan=4, sticky="we")
        ttk.Label(metrics_header, text="Usage and operation averages", font=("Segoe UI", 10, "bold")).pack(side="left")
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
        columns = ("process", "model", "requests", "input_tokens", "output_tokens", "total_tokens",
                   "load", "input", "inference", "model_total", "request", "cost")
        self.metrics_tree = ttk.Treeview(frame, columns=columns, show="headings", height=7)
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
        self.metrics_tree.grid(row=10, column=0, columnspan=4, sticky="we", pady=(6, 0))
        self.metrics_note = ttk.Label(
            frame,
            text="Gateway calls only. Ollama phase times appear when reported; cloud exposes request duration only.",
        )
        self.metrics_note.grid(row=11, column=0, columnspan=4, sticky="w", pady=(4, 0))
        ttk.Separator(frame, orient="horizontal").grid(row=12, column=0, columnspan=4, sticky="we", pady=(12, 8))
        ttk.Label(frame, text="Live process resources", font=("Segoe UI", 10, "bold")).grid(
            row=13, column=0, columnspan=4, sticky="w"
        )
        process_frame = ttk.Frame(frame)
        process_frame.grid(row=14, column=0, columnspan=4, sticky="nsew")
        process_columns = ("name", "pid", "cpu", "memory", "gpu", "gpu_memory")
        self.process_tree = ttk.Treeview(process_frame, columns=process_columns, show="headings", height=8)
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
        process_scroll = ttk.Scrollbar(process_frame, orient="vertical", command=self.process_tree.yview)
        self.process_tree.configure(yscrollcommand=process_scroll.set)
        self.process_tree.pack(side="left", fill="both", expand=True)
        process_scroll.pack(side="right", fill="y")
        self.process_note = ttk.Label(
            frame,
            text="CPU is since the previous refresh. GPU engine utilization and dedicated memory are driver-reported; unavailable values show as —.",
        )
        self.process_note.grid(row=15, column=0, columnspan=4, sticky="w", pady=(4, 0))
        bottom = ttk.Frame(frame)
        bottom.grid(row=16, column=0, columnspan=4, sticky="we", pady=(12, 0))
        ttk.Button(bottom, text="Open chat", command=lambda: self.open_url("open_webui")).pack(side="left")
        ttk.Button(bottom, text="Start all", command=self.start_all).pack(side="left", padx=4)
        ttk.Button(bottom, text="Stop all", command=self.stop_all).pack(side="left")
        ttk.Button(bottom, text="Logs", command=self.open_logs).pack(side="left", padx=4)
        self.startup_var = tk.BooleanVar(value=startup.is_installed())
        ttk.Checkbutton(bottom, text="Start at login", variable=self.startup_var, command=self._toggle_startup).pack(side="right")
        self.window = w

    def _render_window(self) -> None:
        if self.window is None or not self.window.winfo_exists():
            return
        rows = {r["service"]: r for r in self.rows}
        up = 0
        for svc, (dot, state, toggle) in self.row_widgets.items():
            svc_state = rows.get(svc, {}).get("state", "stopped")
            up += svc_state == "running"
            dot.configure(fg=COLORS["ok"] if svc_state == "running" else COLORS["warn"] if svc_state == "starting" else COLORS["bad"])
            state.configure(text=svc_state)
            if toggle is not None:
                toggle.configure(text="Start" if svc_state == "stopped" else "Stop", state="disabled" if self.busy else "normal")
        busy = f"  {self.busy}..." if self.busy else ""
        self.summary.configure(text=f"{up}/{len(self.row_widgets)} running, checked {self.checked_at}{busy}")
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
