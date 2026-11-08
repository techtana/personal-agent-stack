#!/usr/bin/env python3
"""Agent Stack installer window: choose the features, then where the models and Python tools go, then watch setup run
in the background.

Start it with install.cmd (double-click), `.\\scripts\\setup.ps1`, `uv run scripts/stack.py install`, or Add features in
the tray. Page 1 lists the features (stacklib/features.py): required ones are always installed, installed ones stay, and
each row shows what that feature costs on this PC, with the total for the choice underneath. Page 2 asks for the
folders. The window only asks and watches: the work runs in a separate process (stacklib/install.py), so closing the
window does not stop it, and opening the installer again shows how far it got.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stacklib import IS_WINDOWS, REPO  # noqa: E402
from stacklib import features, install  # noqa: E402
from stacklib import profile as prof  # noqa: E402

POLL_MS = 500
WRAP = 840
ERROR_FG = "#a4262c"    # 6.5:1 on the default #f0f0f0 window background
MUTED_FG = "#4d4d4d"    # 7.6:1
OK_FG = "#0e6b0e"       # 6.3:1
WARN_FG = "#7a4f00"     # 6.2:1
MARK = {"pending": ("○", MUTED_FG), "running": ("▶", "#005a9e"), "done": ("✓", OK_FG),
        "skipped": ("–", MUTED_FG), "warning": ("!", WARN_FG), "failed": ("✗", ERROR_FG)}
FINDING = {"ok": ("✓", OK_FG), "warn": ("!", WARN_FG), "bad": ("✗", ERROR_FG)}
COLUMNS = (("disk", "Disk GB"), ("vram", "GPU memory GB"), ("gpu", "GPU work"), ("cpu", "CPU while busy"),
           ("ram", "RAM GB"))
TOOL_NAMES = {"gateway": "LiteLLM", "chat": "Open WebUI", "tracing": "Phoenix"}
# What ticking an installed feature that is off does, when it is not "turn it back on".
TICK_TO = {"openclaw": "Tick it to make the gateway its only model provider (OpenClaw keeps a backup of its config).",
           "recordings": "Tick it to add the server to Claude Desktop again."}


class NoDisplay(Exception):
    """Tk is missing or there is no display to open a window on."""


def open_path(path: Path) -> None:
    if IS_WINDOWS:
        os.startfile(path)  # noqa: S606 - a local folder or log file the installer wrote
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])


def status_text(feat: features.Feature, st: features.Status, is_locked: bool) -> tuple[str, str]:
    """The Status column: words and colour."""
    if feat.required:
        return "Required", MUTED_FG
    if st.unknown:
        return st.state, WARN_FG
    if is_locked:
        return st.state, OK_FG
    if st.installed or st.level in ("warn", "bad"):
        return st.state, ERROR_FG if st.level == "bad" else WARN_FG if st.level == "warn" else MUTED_FG
    return "Not installed", MUTED_FG


class Installer:
    def __init__(self, root, tk, ttk, filedialog):
        self.root, self.tk, self.ttk, self.filedialog = root, tk, ttk, filedialog
        root.title("Agent Stack setup")
        root.minsize(900, 600)
        try:  # the tray's icon on the window and taskbar (Pillow may be missing on a first run)
            from PIL import ImageTk

            from stacklib import procname
            from stacklib.icon import BRAND, make_icon

            procname.set_app_id("installer")
            self.icons = [ImageTk.PhotoImage(make_icon(BRAND, n)) for n in (16, 32, 64)]
            root.iconphoto(True, *self.icons)
        except Exception:  # noqa: BLE001 - only cosmetics
            pass
        self.body = None
        self.d: dict | None = None
        self.step_rows: dict[str, tuple] = {}
        self.behind = None
        self.behind_text = ""
        self.store_msg = self.media_msg = self.summary_box = None
        if install.worker_running():
            self.show_progress()
        else:
            self.show_features()

    def _page(self, scroll: bool = True):
        """A fresh page. With scroll (the two question pages) the content scrolls when it is taller than the screen,
        as the features page is at 150% display scaling, and self.footer below it keeps the buttons in view."""
        tk, ttk = self.tk, self.ttk
        if self.body is not None:
            self.body.destroy()
        self.canvas = None
        if not scroll:
            self.body = ttk.Frame(self.root, padding=16)
            self.body.pack(fill="both", expand=True)
            self.body.columnconfigure(0, weight=1)
            return self.body
        self.body = ttk.Frame(self.root)
        self.body.pack(fill="both", expand=True)
        self.footer = ttk.Frame(self.body, padding=(16, 10, 16, 16))
        self.footer.pack(side="bottom", fill="x")
        bg = ttk.Style(self.root).lookup("TFrame", "background") or self.root.cget("background")
        canvas = self.canvas = tk.Canvas(self.body, highlightthickness=0, borderwidth=0, background=bg)
        bar = ttk.Scrollbar(self.body, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas, padding=(16, 16, 16, 0))
        inner.columnconfigure(0, weight=1)
        item = canvas.create_window(0, 0, window=inner, anchor="nw")

        def fit(_e=None):
            # Ask for the content's size, up to what fits on the screen with the title bar, footer and taskbar.
            room = self.root.winfo_screenheight() - self.footer.winfo_reqheight() - 140
            canvas.configure(scrollregion=(0, 0, inner.winfo_reqwidth(), inner.winfo_reqheight()),
                             width=inner.winfo_reqwidth(), height=min(inner.winfo_reqheight(), max(room, 200)))

        def yset(first, last):
            if float(first) <= 0 and float(last) >= 1:
                bar.pack_forget()
            elif not bar.winfo_manager():
                bar.pack(side="right", fill="y", before=canvas)
            bar.set(first, last)

        inner.bind("<Configure>", fit)
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(item, width=e.width))
        canvas.configure(yscrollcommand=yset)
        canvas.pack(side="left", fill="both", expand=True)
        self.root.bind_all("<MouseWheel>", self._wheel)
        return inner

    def _wheel(self, e):
        canvas = self.canvas
        if canvas is not None and canvas.winfo_exists() and e.delta:
            canvas.yview_scroll(-round(e.delta / 120) or (-1 if e.delta > 0 else 1), "units")

    @staticmethod
    def _alive(widget) -> bool:
        return widget is not None and bool(widget.winfo_exists())

    # ------------------------------------------------------------ the choices, kept across both pages

    def _load(self):
        """Read this PC and the profile, and make the variables both pages edit, so Back and Next keep the choices."""
        tk = self.tk
        prof.write_profile()
        self.profile = prof.resolve_profile()
        d = self.d = install.defaults(self.profile)
        self.feature_vars = {fid: tk.BooleanVar(value=on) for fid, on in d["choice"].items()}
        self.store = tk.StringVar(value=d["model_store"])
        self.tools = tk.StringVar(value=d["tool_dir"])
        self.media_root = tk.StringVar(value=d["media_root"])
        self.pull = tk.BooleanVar(value=True)
        self.move = tk.BooleanVar(value=bool(d["move_from"]))
        self.get_ollama = tk.BooleanVar(value=d["ollama_missing"])
        self.start = tk.BooleanVar(value=True)
        self.disks = tk.BooleanVar(value=True)
        self.hf = tk.BooleanVar(value=True)
        for v in (self.store, self.tools, self.media_root):
            v.trace_add("write", lambda *_: self.validate())
        self._check_checkout()

    def chosen(self) -> set[str]:
        return {fid for fid, v in self.feature_vars.items() if v.get()}

    def _check_checkout(self):
        """Fetch in a thread (it can take seconds, or time out offline) and show the warning on whichever page is up."""
        result: list[str] = []
        threading.Thread(target=lambda: result.append(install.checkout_behind()), daemon=True).start()

        def done():
            if not result:
                self.root.after(POLL_MS, done)
                return
            self.behind_text = result[0]
            self._show_behind()
        self.root.after(POLL_MS, done)

    def _behind_label(self, parent):
        self.behind = self.ttk.Label(parent, text="", foreground=WARN_FG, wraplength=WRAP)
        self.behind.grid(sticky="w")
        self._show_behind()

    def _show_behind(self):
        if self.behind_text and self._alive(self.behind):
            self.behind.configure(text=self.behind_text)
            self.behind.grid_configure(pady=(0, 10))

    # ------------------------------------------------------------ page 1: features

    def show_features(self, reload: bool = False):
        ttk = self.ttk
        if reload or self.d is None:
            self._load()
        d = self.d
        f = self._page()
        ttk.Label(f, text="Which features do you want?", font=("Segoe UI", 13, "bold")).grid(sticky="w")
        ttk.Label(f, wraplength=WRAP, text="The required parts are always installed, and installed features stay. "
                  "Tick the others you want; run the installer again later to add more. Settings in the tray turns "
                  "off Open WebUI, Phoenix, images and voice typing.").grid(sticky="w", pady=(4, 2))
        ttk.Label(f, wraplength=WRAP, foreground=MUTED_FG,
                  text=f"This PC: {d['hardware'].describe()}. Each row is one feature on its own; the box at the "
                       "bottom adds up your choice.").grid(sticky="w", pady=(0, 10))
        self._behind_label(f)

        table = ttk.Frame(f)
        table.grid(sticky="ew")
        table.columnconfigure(0, weight=1)
        for c, head in enumerate(("Feature", "Status", *(title for _key, title in COLUMNS))):
            ttk.Label(table, text=head, foreground=MUTED_FG, font=("Segoe UI", 9, "bold")).grid(
                row=0, column=c, sticky="w" if c < 2 else "e", padx=(0 if c == 0 else 14, 0), pady=(0, 4))
        first = None
        self.feature_boxes = {}
        for r, feat in enumerate(features.FEATURES, start=1):
            st, is_locked = d["features"][feat.id], features.locked(feat.id, d["features"])
            box = self.feature_boxes[feat.id] = ttk.Checkbutton(table, text=feat.title, command=self.update_summary,
                                                                 variable=self.feature_vars[feat.id])
            if is_locked:
                box.state(["disabled"])   # required, or installed and on: Settings in the tray turns it off
            elif first is None:
                first = feat.id
            box.grid(row=r, column=0, sticky="w", pady=2)
            text, fg = status_text(feat, st, is_locked)
            row = [box, ttk.Label(table, text=text, foreground=fg)]
            row[1].grid(row=r, column=1, sticky="w", padx=(14, 0))
            values = features.cells(d["estimates"][feat.id], d["hardware"])
            for c, (key, _title) in enumerate(COLUMNS, start=2):
                row.append(ttk.Label(table, text=values[key]))
                row[-1].grid(row=r, column=c, sticky="e", padx=(14, 0))
            for w in row:   # the box below explains the row under the pointer, or the one with keyboard focus
                w.bind("<Enter>", lambda _e, fid=feat.id: self.show_detail(fid), add="+")
            box.bind("<FocusIn>", lambda _e, fid=feat.id: self.show_detail(fid), add="+")

        self.detail_box = ttk.LabelFrame(f, text="", padding=10)
        self.detail_box.grid(sticky="ew", pady=(10, 0))
        self.detail = ttk.Label(self.detail_box, text="", wraplength=WRAP - 30, justify="left")
        self.detail.grid(sticky="w")
        self.summary_box = ttk.LabelFrame(f, text="Your choice on this PC", padding=10)
        self.summary_box.grid(sticky="ew", pady=(10, 0))
        self.summary_box.columnconfigure(1, weight=1)
        ttk.Button(self.footer, text="Cancel", command=self.root.destroy).pack(side="right")
        ttk.Button(self.footer, text="Next", command=self.show_folders, default="active").pack(side="right", padx=(0, 8))
        self.root.bind("<Return>", lambda e: self.show_folders())
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.show_detail(first or features.FEATURES[0].id)
        self.update_summary()

    def show_detail(self, fid: str):
        if not self._alive(getattr(self, "detail", None)):
            return
        feat, d = features.BY_ID[fid], self.d
        st = d["features"][fid]
        lines = [feat.summary]
        if feat.required:
            lines.append("Required: the other features use it." + (f" {st.detail}" if st.level != "ok" else ""))
        elif st.unknown:
            lines.append(f"Not checked ({st.detail}), so the installer leaves it as it is.")
        elif features.locked(fid, d["features"]):
            if fid in install.FEATURE_SWITCHES:
                lines.append(f"{st.state}: setup checks it again. To turn it off, use Settings in the tray.")
            else:
                lines.append(f"{st.state}: setup leaves it as it is.")
        elif st.installed:
            lines.append(f"{st.state}. {st.detail} {TICK_TO.get(fid, 'Tick it to turn it back on.')}")
        elif st.level in ("warn", "bad"):
            lines.append(f"{st.state}. {st.detail}")
        lines.append(features.detail_text(d["estimates"][fid]))
        self.detail_box.configure(text=feat.title)
        self.detail.configure(text="\n".join(lines))

    def update_summary(self):
        if not self._alive(self.summary_box):
            return
        ttk, d = self.ttk, self.d
        for child in self.summary_box.winfo_children():
            child.destroy()
        installed = {fid for fid, s in d["features"].items() if s.installed}
        for i, finding in enumerate(features.assess(self.chosen(), d["estimates"], d["hardware"], installed)):
            sym, fg = FINDING.get(finding.level, FINDING["ok"])
            ttk.Label(self.summary_box, text=sym, foreground=fg, width=2, font=("Segoe UI", 11)).grid(
                row=i, column=0, sticky="nw")
            text = ttk.Label(self.summary_box, text=finding.text, wraplength=WRAP - 60, justify="left")
            if finding.level != "ok":
                text.configure(foreground=fg)
            text.grid(row=i, column=1, sticky="w", pady=1)

    # ------------------------------------------------------------ page 2: folders and options

    def show_folders(self):
        ttk, d = self.ttk, self.d
        chosen = self.chosen()
        f = self._page()
        ttk.Label(f, text="Where should Agent Stack put its files?", font=("Segoe UI", 13, "bold")).grid(sticky="w")
        ttk.Label(f, wraplength=WRAP, text="Choose the folders, then Install. Setup runs in the background: you can "
                  "close this window while it works and open the installer again to check on it.").grid(sticky="w", pady=(4, 12))
        self._behind_label(f)
        self.store_msg = self._folder(f, "Models (Ollama)", "Downloaded models live here. Needs the most space; "
                                      "a fast internal drive loads models quicker than a USB one.", self.store, d["model_note"])
        tools = ", ".join(name for fid, name in TOOL_NAMES.items() if fid in install.chosen_with_required(chosen))
        self.tools_msg = self._folder(f, f"Python tools ({tools})",
                                      "Each tool gets its own Python environment here. Keep the path short.", self.tools)
        self.media_msg = None
        if install.needs_media(chosen):
            what = " and ".join(n for fid, n in (("images", "ComfyUI with the image model"),
                                                 ("recordings", "Whisper for recordings")) if fid in chosen)
            installed = any(d["features"][fid].installed for fid in ("images", "recordings") if fid in chosen)
            self.media_msg = self._folder(f, "Media (ComfyUI, Whisper and their models)",
                                          f"{what[0].upper()}{what[1:]} go here. Agent sessions and media tools may use "
                                          "only this folder.", self.media_root,
                                          "Installed already: setup checks and updates it." if installed else "")

        opts = ttk.LabelFrame(f, text="Options", padding=10)
        opts.grid(sticky="ew", pady=(4, 0))
        ttk.Checkbutton(opts, variable=self.pull, command=self.validate,
                        text=f"Download models now: {', '.join(d['models'])} (about {d['models_gb']:.1f} GB)").grid(sticky="w")
        self.move_box = None
        if d["move_from"]:   # shown by validate() only while the models folder differs from where they are
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
        ttk.Checkbutton(opts, variable=self.start, text="Start the stack when setup finishes (tray app)").grid(sticky="w")

        self.error = ttk.Label(f, text="", foreground=ERROR_FG, wraplength=WRAP)
        self.error.grid(sticky="w", pady=(8, 0))
        ttk.Button(self.footer, text="Back", command=self.show_features).pack(side="left")
        ttk.Button(self.footer, text="Cancel", command=self.root.destroy).pack(side="right")
        self.install_btn = ttk.Button(self.footer, text="Install", command=self.on_install, default="active")
        self.install_btn.pack(side="right", padx=(0, 8))
        self.root.bind("<Return>", lambda e: self.on_install())
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.validate()

    def _folder(self, parent, title, hint, var, note=""):
        ttk = self.ttk
        box = ttk.LabelFrame(parent, text=title, padding=10)
        box.grid(sticky="ew", pady=(0, 10))
        box.columnconfigure(0, weight=1)
        ttk.Label(box, text=hint, foreground=MUTED_FG, wraplength=WRAP - 40).grid(row=0, column=0, columnspan=2, sticky="w")
        entry = ttk.Entry(box, textvariable=var)
        entry.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(box, text="Browse...", command=lambda: self.browse(var, title)).grid(row=1, column=1, padx=(8, 0), pady=(6, 0))
        msg = ttk.Label(box, text="", wraplength=WRAP - 40)
        msg.grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))
        if note:
            ttk.Label(box, text=note, foreground=MUTED_FG, wraplength=WRAP - 40).grid(row=3, column=0, columnspan=2, sticky="w", pady=(2, 0))
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

    def needs(self) -> tuple[float, float, float]:
        """GB the models, tools and media folders need for this choice: only what is not installed there yet."""
        d, chosen = self.d, self.chosen()
        store_gb = install.store_need_gb(d, self.profile, self.store.get().strip(), self.pull.get(),
                                         d["move_from"] if self._moving() else "")
        tools = self.tools.get().strip()
        moving_tools = bool(d["tool_dir"]) and bool(tools) and Path(tools) != Path(d["tool_dir"])
        tools_gb = install.tools_need_gb(chosen, d["estimates"], d["features"], moving_tools)
        media_gb = install.media_need_gb(chosen, d["estimates"], d["features"],
                                         install.media_moved(self.profile, self.media_root.get().strip()))
        return store_gb, tools_gb, media_gb

    def validate(self) -> bool:
        if not self._alive(self.store_msg):
            return False   # page 1 is showing: the folders are checked on page 2
        self.hf_box.configure(text=f"Put the Hugging Face cache in {install.default_hf_home(self.store.get().strip())} "
                              "(HF_HOME) and install the hf command")
        if self.move_box is not None:
            store = self.store.get().strip()
            if store and Path(store) != Path(self.d["move_from"]):
                self.move_box.grid()
            else:
                self.move_box.grid_remove()
        store_gb, tools_gb, media_gb = self.needs()
        checks = [(self.store, self.store_msg, store_gb), (self.tools, self.tools_msg, tools_gb)]
        if self.media_msg is not None:
            checks.append((self.media_root, self.media_msg, media_gb))
        ok = True
        for var, label, need in checks:
            chk = install.check_dir(var.get(), need)
            label.configure(text=chk.message, foreground=OK_FG if chk.ok else ERROR_FG)
            ok &= chk.ok
        self.install_btn.state(["!disabled"] if ok else ["disabled"])
        return ok

    def on_install(self):
        if not self.validate():
            return
        chosen = self.chosen()
        store = str(Path(self.store.get().strip()).expanduser())
        tools = str(Path(self.tools.get().strip()).expanduser())
        media_root = str(Path(self.media_root.get().strip()).expanduser()) if install.needs_media(chosen) else ""
        try:
            for path in (store, tools):
                Path(path).mkdir(parents=True, exist_ok=True)
            install.save_paths(self.profile, store)
            install.save_features(self.profile, chosen, media_root, self.d["features"])
            plan = install.Plan(
                model_store=store,
                tool_dir="" if self.d["tool_dir"] and Path(tools) == Path(self.d["tool_dir"]) else tools,
                move_models_from=self.d["move_from"] if self._moving() else "",
                install_ollama=self.d["ollama_missing"] and self.get_ollama.get(),
                pull=self.pull.get(),
                start_stack=self.start.get(),
                check_disks=self.disks.get(),
                setup_huggingface=self.hf.get(),
                media_root=media_root,
                **install.feature_plan(chosen, self.d["features"]),
            )
            install.spawn_worker(plan)
        except (OSError, ValueError, RuntimeError) as e:
            self.error.configure(text=f"Could not start setup: {e}")
            return
        self.root.unbind("<Return>")
        self.show_progress()

    # ------------------------------------------------------------ page 3: progress

    def show_progress(self):
        tk, ttk = self.tk, self.ttk
        f = self._page(scroll=False)   # the log box takes the spare height instead
        self.heading = ttk.Label(f, text=install.summary({"status": "running"}), font=("Segoe UI", 13, "bold"))
        self.heading.grid(sticky="w")
        self.subheading = ttk.Label(f, wraplength=WRAP, foreground=MUTED_FG,
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
            detail = ttk.Label(steps, text="", foreground=MUTED_FG, wraplength=480)
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
        self.retry_btn = ttk.Button(buttons, text="Change choices and run again",
                                    command=lambda: self.show_features(reload=True))
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
                "done": f"Next: {self._next_step()}",
                "warnings": f"Everything ran; the steps marked ! say what to look at. Then: {self._next_step()}",
                "failed": "The failed steps say what went wrong; the log has the details. Fix it, then run setup again.",
                "interrupted": "Run setup again to finish; steps that already ran are quick the second time.",
            }.get(status, ""))
            if status in ("failed", "interrupted", "done", "warnings"):
                self.retry_btn.pack(side="right", padx=(0, 8))

    @staticmethod
    def _next_step() -> str:
        """What to open first: the chat when Open WebUI is on, else the tray, whose Features card lists what is in."""
        try:
            p = prof.resolve_profile()
        except (OSError, ValueError):
            return "open the tray (Agent Stack in the Start menu)."
        if p["services"].get("open_webui") == "native":
            return (f"open http://127.0.0.1:{p['ports']['open_webui']} for chat. The tray's Features card lists what "
                    "is installed.")
        return "open the tray (Agent Stack in the Start menu); its Features card lists what is installed."

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
