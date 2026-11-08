#!/usr/bin/env python3
"""Agent Stack installer window: choose where the models and Python tools go, then watch setup run in the background.

Start it with install.cmd (double-click), `.\\scripts\\setup.ps1` or `uv run scripts/stack.py install`. The window only
asks and watches: the work runs in a separate process (stacklib/install.py), so closing the window does not stop it,
and opening the installer again shows how far it got.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stacklib import IS_WINDOWS, REPO  # noqa: E402
from stacklib import install  # noqa: E402
from stacklib import profile as prof  # noqa: E402

POLL_MS = 500
ERROR_FG = "#a4262c"    # 6.5:1 on the default #f0f0f0 window background
MUTED_FG = "#4d4d4d"    # 7.6:1
OK_FG = "#0e6b0e"       # 6.3:1
WARN_FG = "#7a4f00"     # 6.2:1
MARK = {"pending": ("○", MUTED_FG), "running": ("▶", "#005a9e"), "done": ("✓", OK_FG),
        "skipped": ("–", MUTED_FG), "warning": ("!", WARN_FG), "failed": ("✗", ERROR_FG)}


class NoDisplay(Exception):
    """Tk is missing or there is no display to open a window on."""


def open_path(path: Path) -> None:
    if IS_WINDOWS:
        os.startfile(path)  # noqa: S606 - a local folder or log file the installer wrote
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])


class Installer:
    def __init__(self, root, tk, ttk, filedialog):
        self.root, self.tk, self.ttk, self.filedialog = root, tk, ttk, filedialog
        root.title("Agent Stack setup")
        root.minsize(680, 520)
        self.body = None
        self.step_rows: dict[str, tuple] = {}
        if install.worker_running():
            self.show_progress()
        else:
            self.show_choices()

    def _page(self):
        if self.body is not None:
            self.body.destroy()
        self.body = self.ttk.Frame(self.root, padding=16)
        self.body.pack(fill="both", expand=True)
        self.body.columnconfigure(0, weight=1)
        return self.body

    # ------------------------------------------------------------ page 1: choices

    def show_choices(self):
        tk, ttk = self.tk, self.ttk
        prof.write_profile()
        self.profile = prof.resolve_profile()
        d = self.d = install.defaults(self.profile)
        f = self._page()
        ttk.Label(f, text="Where should Agent Stack put its files?", font=("Segoe UI", 13, "bold")).grid(sticky="w")
        ttk.Label(f, wraplength=640, text="Choose the folders, then Install. Setup runs in the background: you can "
                  "close this window while it works and open the installer again to check on it.").grid(sticky="w", pady=(4, 12))
        self.behind = ttk.Label(f, text="", foreground=WARN_FG, wraplength=640)
        self.behind.grid(sticky="w")
        self._check_checkout()

        self.store = tk.StringVar(value=d["model_store"])
        self.tools = tk.StringVar(value=d["tool_dir"])
        self.pull = tk.BooleanVar(value=True)
        self.move = tk.BooleanVar(value=bool(d["move_from"]))
        self.get_ollama = tk.BooleanVar(value=d["ollama_missing"])
        self.start = tk.BooleanVar(value=True)
        self.disks = tk.BooleanVar(value=True)
        self.hf = tk.BooleanVar(value=True)
        self.openclaw = tk.BooleanVar(value=not d["openclaw_installed"] or bool(d["openclaw_state"]))
        self.media_root = tk.StringVar(value=d["media_root"])
        self.media = tk.BooleanVar(value=True)

        self.store_msg = self._folder(f, "Models (Ollama)", "Downloaded models live here. Needs the most space; "
                                      "a fast internal drive loads models quicker than a USB one.", self.store, d["model_note"])
        self.tools_msg = self._folder(f, "Python tools (LiteLLM, Phoenix, Open WebUI)",
                                      "Each tool gets its own Python environment here. Keep the path short.", self.tools)
        self.media_msg = self._folder(f, "Media (ComfyUI and image models)",
                                      "Image generation for the chat's image button: ComfyUI, PyTorch and the Z-Image-Turbo "
                                      "model (Apache-2.0). Agent sessions and media tools may use only this folder.",
                                      self.media_root, "Installed already: setup updates it." if d["media_installed"] else "")

        opts = ttk.LabelFrame(f, text="Options", padding=10)
        opts.grid(sticky="ew", pady=(4, 0))
        ttk.Checkbutton(opts, variable=self.pull, command=self.validate,
                        text=f"Download models now: {', '.join(d['models'])} (about {d['models_gb']:.1f} GB)").grid(sticky="w")
        if d["move_from"]:
            self.move_box = ttk.Checkbutton(opts, variable=self.move, command=self.validate,
                                            text=f"Move the {d['move_gb']:.1f} GB of models already in {d['move_from']}")
            self.move_box.grid(sticky="w")
        if d["ollama_missing"]:
            ttk.Checkbutton(opts, variable=self.get_ollama, text="Install Ollama with winget (it is not installed; "
                            "accepts the Ollama package agreement)").grid(sticky="w")
        ttk.Checkbutton(opts, variable=self.disks, text="Check how fast each drive is and warn about slow ones "
                        "(writes a 256 MB test file per drive)").grid(sticky="w")
        self.hf_box = ttk.Checkbutton(opts, variable=self.hf)
        self.hf_box.grid(sticky="w")
        if not d["openclaw_installed"]:
            ttk.Checkbutton(opts, variable=self.openclaw, text="Install OpenClaw with npm and point it at this stack's "
                            "gateway (upgrades Node.js with winget first if it is too old; Windows asks for admin)").grid(sticky="w")
        elif d["openclaw_state"]:
            ttk.Checkbutton(opts, variable=self.openclaw, text=f"Point OpenClaw at this stack's gateway (now: "
                            f"{d['openclaw_state'].lower()}; OpenClaw keeps a backup of its config)").grid(sticky="w")
        ttk.Checkbutton(opts, variable=self.media, command=self.validate,
                        text=f"Install ComfyUI and the image model in the media folder (about {install.MEDIA_GB:.0f} GB)").grid(sticky="w")
        ttk.Checkbutton(opts, variable=self.start, text="Start the stack when setup finishes (tray app)").grid(sticky="w")

        self.error = ttk.Label(f, text="", foreground=ERROR_FG, wraplength=640)
        self.error.grid(sticky="w", pady=(8, 0))
        f.rowconfigure(98, weight=1)
        buttons = ttk.Frame(f)
        buttons.grid(row=99, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="Cancel", command=self.root.destroy).pack(side="right")
        self.install_btn = ttk.Button(buttons, text="Install", command=self.on_install, default="active")
        self.install_btn.pack(side="right", padx=(0, 8))
        self.root.bind("<Return>", lambda e: self.on_install())
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        for v in (self.store, self.tools, self.media_root):
            v.trace_add("write", lambda *_: self.validate())
        self.validate()

    def _check_checkout(self):
        """Fetch in a thread (it can take seconds, or time out offline) and show the warning when it is back."""
        result: list[str] = []
        threading.Thread(target=lambda: result.append(install.checkout_behind()), daemon=True).start()

        def done():
            if not result:
                self.root.after(POLL_MS, done)
            elif result[0] and self.behind.winfo_exists():
                self.behind.configure(text=result[0])
                self.behind.grid_configure(pady=(0, 12))
        self.root.after(POLL_MS, done)

    def _folder(self, parent, title, hint, var, note=""):
        ttk = self.ttk
        box = ttk.LabelFrame(parent, text=title, padding=10)
        box.grid(sticky="ew", pady=(0, 10))
        box.columnconfigure(0, weight=1)
        ttk.Label(box, text=hint, foreground=MUTED_FG, wraplength=600).grid(row=0, column=0, columnspan=2, sticky="w")
        entry = ttk.Entry(box, textvariable=var)
        entry.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(box, text="Browse...", command=lambda: self.browse(var, title)).grid(row=1, column=1, padx=(8, 0), pady=(6, 0))
        msg = ttk.Label(box, text="", wraplength=600)
        msg.grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))
        if note:
            ttk.Label(box, text=note, foreground=MUTED_FG, wraplength=600).grid(row=3, column=0, columnspan=2, sticky="w", pady=(2, 0))
        return msg

    def browse(self, var, title):
        start = var.get()
        while start and not os.path.isdir(start) and os.path.dirname(start) != start:
            start = os.path.dirname(start)
        chosen = self.filedialog.askdirectory(parent=self.root, title=title, initialdir=start or str(Path.home()), mustexist=False)
        if chosen:
            var.set(str(Path(chosen)))

    def _moving(self) -> bool:
        d = self.d
        return bool(d["move_from"] and self.move.get() and self.store.get().strip()
                    and Path(self.store.get().strip()) != Path(d["move_from"]))

    def needs(self) -> tuple[float, float]:
        d = self.d
        store_gb = d["models_gb"] if self.pull.get() else 0.1
        if self._moving() and not install.same_drive(d["move_from"], self.store.get().strip()):
            store_gb += d["move_gb"]
        tools = self.tools.get().strip()
        changed = bool(d["tool_dir"]) and tools and Path(tools) != Path(d["tool_dir"])
        tools_gb = install.TOOLS_GB if d["tools_missing"] or changed else 0.1
        return store_gb, tools_gb

    def validate(self) -> bool:
        self.hf_box.configure(text=f"Put the Hugging Face cache in {install.default_hf_home(self.store.get().strip())} "
                              "(HF_HOME) and install the hf command")
        store_gb, tools_gb = self.needs()
        ok = True
        media_gb = install.MEDIA_GB if self.media.get() and not self.d["media_installed"] else 0.1
        checks = [(self.store, self.store_msg, store_gb), (self.tools, self.tools_msg, tools_gb)]
        if self.media.get():
            checks.append((self.media_root, self.media_msg, media_gb))
        else:
            self.media_msg.configure(text="Not chosen: the chat has no image button.", foreground=MUTED_FG)
        for var, label, need in checks:
            chk = install.check_dir(var.get(), need)
            label.configure(text=chk.message, foreground=OK_FG if chk.ok else ERROR_FG)
            ok &= chk.ok
        self.install_btn.state(["!disabled"] if ok else ["disabled"])
        return ok

    def on_install(self):
        if not self.validate():
            return
        store = str(Path(self.store.get().strip()).expanduser())
        tools = str(Path(self.tools.get().strip()).expanduser())
        try:
            for path in (store, tools):
                Path(path).mkdir(parents=True, exist_ok=True)
            install.save_paths(self.profile, store)
            plan = install.Plan(
                model_store=store,
                tool_dir="" if self.d["tool_dir"] and Path(tools) == Path(self.d["tool_dir"]) else tools,
                move_models_from=self.d["move_from"] if self._moving() else "",
                install_ollama=self.d["ollama_missing"] and self.get_ollama.get(),
                pull=self.pull.get(),
                start_stack=self.start.get(),
                check_disks=self.disks.get(),
                setup_huggingface=self.hf.get(),
                install_openclaw=not self.d["openclaw_installed"] and self.openclaw.get(),
                setup_openclaw=self.openclaw.get(),
                setup_media=self.media.get(),
                media_root=str(Path(self.media_root.get().strip()).expanduser()) if self.media.get() else "",
            )
            install.spawn_worker(plan)
        except (OSError, ValueError, RuntimeError) as e:
            self.error.configure(text=f"Could not start setup: {e}")
            return
        self.root.unbind("<Return>")
        self.show_progress()

    # ------------------------------------------------------------ page 2: progress

    def show_progress(self):
        tk, ttk = self.tk, self.ttk
        f = self._page()
        self.heading = ttk.Label(f, text=install.summary({"status": "running"}), font=("Segoe UI", 13, "bold"))
        self.heading.grid(sticky="w")
        self.subheading = ttk.Label(f, wraplength=640, foreground=MUTED_FG,
                                    text="You can close this window; setup keeps running. Open the installer again to see where it is.")
        self.subheading.grid(sticky="w", pady=(4, 10))
        steps = ttk.Frame(f)
        steps.grid(sticky="ew")
        steps.columnconfigure(2, weight=1)
        self.step_rows = {}
        for i, (sid, title, _) in enumerate(install.STEPS):
            mark = ttk.Label(steps, text=MARK["pending"][0], foreground=MARK["pending"][1], width=2, font=("Segoe UI", 11))
            mark.grid(row=i, column=0, sticky="nw")
            ttk.Label(steps, text=title).grid(row=i, column=1, sticky="nw", padx=(0, 12))
            detail = ttk.Label(steps, text="", foreground=MUTED_FG, wraplength=380)
            detail.grid(row=i, column=2, sticky="nw")
            self.step_rows[sid] = (mark, detail)
        self.bar = ttk.Progressbar(f, mode="determinate", maximum=1.0)
        self.bar.grid(sticky="ew", pady=(10, 6))
        f.rowconfigure(4, weight=1)
        logbox = ttk.Frame(f)
        logbox.grid(row=4, sticky="nsew")
        logbox.columnconfigure(0, weight=1)
        logbox.rowconfigure(0, weight=1)
        self.log = tk.Text(logbox, height=10, wrap="none", font=("Consolas", 9), state="disabled", relief="flat",
                           background="#ffffff", foreground="#1a1a1a", borderwidth=1, highlightthickness=1)
        self.log.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(logbox, command=self.log.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=sb.set)
        buttons = ttk.Frame(f)
        buttons.grid(row=5, sticky="ew", pady=(12, 0))
        ttk.Button(buttons, text="Open log", command=lambda: open_path(install.LOG_FILE)).pack(side="left")
        ttk.Button(buttons, text="Close", command=self.root.destroy).pack(side="right")
        self.retry_btn = ttk.Button(buttons, text="Change folders and run again", command=self.show_choices)
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self._log_size = -1
        self.poll()

    def poll(self):
        if self.body is None or not self.body.winfo_exists() or not self.step_rows:
            return
        state = install.read_state()
        status = state.get("status", "running")
        self.heading.configure(text=install.summary(state) if state else "Starting setup...")
        running = None
        for s in state.get("steps", []):
            mark, detail = self.step_rows.get(s["id"], (None, None))
            if mark is None:
                continue
            sym, fg = MARK.get(s["status"], MARK["pending"])
            mark.configure(text=sym, foreground=fg)
            word = {"skipped": "Skipped: ", "warning": "Warning: ", "failed": "Failed: "}.get(s["status"], "")
            detail.configure(text=word + s["detail"] if s["detail"] else word.rstrip(": "),
                             foreground={"failed": ERROR_FG, "warning": WARN_FG}.get(s["status"], MUTED_FG))
            if s["status"] == "running":
                running = s
        if running and running.get("fraction") is not None:
            if str(self.bar.cget("mode")) != "determinate":
                self.bar.stop()
                self.bar.configure(mode="determinate")
            self.bar["value"] = running["fraction"]
        elif running:
            if str(self.bar.cget("mode")) != "indeterminate":
                self.bar.configure(mode="indeterminate")
                self.bar.start(15)
        else:
            self.bar.stop()
            self.bar.configure(mode="determinate")
            self.bar["value"] = 1.0 if status in ("done", "warnings") else self.bar["value"]
        self._tail_log()
        if status in ("running",) or not state:
            self.root.after(POLL_MS, self.poll)
        else:
            self.subheading.configure(text={
                "done": "Next: open http://127.0.0.1:3000 for chat, or run `uv run scripts/stack.py smoke` to check the gateway.",
                "warnings": "Everything ran; the steps marked ! say what to look at. Then open http://127.0.0.1:3000 for chat.",
                "failed": "The failed steps say what went wrong; the log has the details. Fix it, then run setup again.",
                "interrupted": "Run setup again to finish; steps that already ran are quick the second time.",
            }.get(status, ""))
            if status in ("failed", "interrupted"):
                self.retry_btn.pack(side="right", padx=(0, 8))

    def _tail_log(self):
        try:
            size = install.LOG_FILE.stat().st_size
        except OSError:
            return
        if size == self._log_size:
            return
        self._log_size = size
        with open(install.LOG_FILE, "rb") as fh:
            fh.seek(max(0, size - 20_000))
            text = fh.read().decode("utf-8", "replace").replace("\r\n", "\n")
        # uv and winget redraw progress bars with carriage returns: keep only the last state of each line
        lines = [ln.rsplit("\r", 1)[-1] for ln in text.split("\n")][-200:]
        at_end = self.log.yview()[1] >= 0.999
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.insert("end", "\n".join(lines))
        self.log.configure(state="disabled")
        if at_end:
            self.log.see("end")


def main() -> int:
    if IS_WINDOWS:
        try:
            import ctypes

            # install.cmd starts python.exe (Smart App Control blocks the venv's pythonw.exe); hide its console window.
            # Only when install.cmd asked, so a terminal running `stack.py install` stays visible.
            if os.environ.get("AGENT_STACK_HIDE_CONSOLE") == "1":
                ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
            ctypes.windll.shcore.SetProcessDpiAwareness(1)   # sharp text on scaled displays; must precede Tk()
        except (AttributeError, OSError):
            pass
    try:
        import tkinter as tk
        from tkinter import filedialog, ttk

        root = tk.Tk()
    except Exception as e:  # noqa: BLE001 - ImportError without Tk, TclError without a display
        raise NoDisplay(str(e)) from e
    Installer(root, tk, ttk, filedialog)
    root.mainloop()
    return 0


def report_crash() -> None:
    """Under pythonw (install.cmd) a traceback has nowhere to go: keep it in a file and say so in a message box."""
    import traceback

    path = install.INSTALL_DIR / "installer-error.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(traceback.format_exc(), encoding="utf-8")
    try:
        from tkinter import Tk, messagebox

        Tk().withdraw()
        messagebox.showerror("Agent Stack setup", f"The installer stopped with an error. Details are in {path}")
    except Exception:  # noqa: BLE001 - no display either; the file is all there is
        pass


if __name__ == "__main__":
    os.chdir(REPO)
    try:
        raise SystemExit(main())
    except NoDisplay as e:
        print(f"no window available ({e}); run `uv run scripts/stack.py install --no-gui`", file=sys.stderr)
        raise SystemExit(1)
    except Exception:  # noqa: BLE001
        report_crash()
        raise
