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

from stacklib import REPO, profile as prof, services  # noqa: E402
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
        healthy = any(r["service"] == svc and r["healthy"] for r in self.rows)
        if healthy:
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
        w.resizable(False, False)
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
        bottom = ttk.Frame(frame)
        bottom.grid(row=20, column=0, columnspan=4, sticky="we", pady=(12, 0))
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
            healthy = bool(rows.get(svc, {}).get("healthy"))
            up += healthy
            dot.configure(fg=COLORS["ok"] if healthy else COLORS["bad"])
            state.configure(text="running" if healthy else "stopped")
            if toggle is not None:
                toggle.configure(text="Stop" if healthy else "Start", state="disabled" if self.busy else "normal")
        busy = f"  {self.busy}..." if self.busy else ""
        self.summary.configure(text=f"{up}/{len(self.row_widgets)} running, checked {self.checked_at}{busy}")
        self.startup_var.set(startup.is_installed())

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
