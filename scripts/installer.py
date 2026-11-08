#!/usr/bin/env python3
"""Agent Stack installer window: choose the features, then where the models and Python tools go, then watch setup run
in the background.

Start it with install.cmd (double-click), `.\\scripts\\setup.ps1`, `uv run scripts/stack.py install`, or Open installer in
the tray. Page 1 lists the features (stacklib/features.py): required ones are always installed, installed ones stay
unless their Remove box is ticked, and each row shows what that feature costs on this PC, with the total for the choice
underneath; downloaded models the stack does not use can be ticked for deletion too. Page 2 asks for the folders. The
window only asks and watches: the work runs in a separate process (stacklib/install.py, and stacklib/uninstall.py for
removals), so closing the window does not stop it, and opening the installer again shows how far it got.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stacklib import IS_WINDOWS, REPO  # noqa: E402
from stacklib import features, install, theme, uninstall  # noqa: E402
from stacklib import profile as prof  # noqa: E402

POLL_MS = 500
WRAP = 840
HALF = 430   # wrap width in each of the two cards under the features table
GAP_S, GAP_M, GAP_L, GAP_XL = 8, 12, 16, 24   # the tray's spacing tokens
FONT = theme.FONT
# Marks and colours by palette key (stacklib/theme.py), so the light and dark themes both pass 4.5:1 on the card.
MARK = {"pending": ("○", "muted"), "running": ("●", "accent"), "done": ("✓", "good"),
        "skipped": ("–", "muted"), "warning": ("!", "warn"), "failed": ("✗", "bad")}
FINDING = {"ok": ("✓", "good"), "warn": ("!", "warn"), "bad": ("✗", "bad")}
WIZARD = ("Features", "Folders", "Install")   # the three pages, shown as steps at the top of each
COLUMNS = (("disk", "Disk GB"), ("vram", "GPU memory GB"), ("gpu", "GPU work"), ("cpu", "CPU while busy"),
           ("ram", "RAM GB"))
TOOL_NAMES = {"gateway": "LiteLLM", "chat": "Open WebUI", "tracing": "Phoenix"}
# Feature states with something on disk to remove although the feature reads as not (fully) installed.
REPAIRABLE = {"Model missing", "Files missing"}
# What ticking an installed feature that is off does, when it is not "turn it back on".
TICK_TO = {"openclaw": "Tick it to make the gateway its only model provider (OpenClaw keeps a backup of its config)."}


class NoDisplay(Exception):
    """Tk is missing or there is no display to open a window on."""


def open_path(path: Path) -> None:
    if IS_WINDOWS:
        os.startfile(path)  # noqa: S606 - a local folder or log file the installer wrote
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])


def status_text(feat: features.Feature, st: features.Status, is_locked: bool) -> tuple[str, str]:
    """The Status column: words and a palette key. Green means installed and working; amber and red say what to look
    at; everything else (required, off, not installed) stays in the quiet ink2, so colour marks only state."""
    if feat.required:
        return "Required", "ink2"
    if st.unknown:
        return st.state, "warn"
    if st.level in ("warn", "bad"):
        return st.state, st.level
    if is_locked:
        return st.state, "good"
    if st.installed:
        return st.state, "ink2"
    return "Not installed", "ink2"


class Installer:
    def __init__(self, root, tk, ttk, filedialog):
        self.root, self.tk, self.ttk, self.filedialog = root, tk, ttk, filedialog
        root.title("Agent Stack setup")
        root.minsize(900, 600)
        # The tray's look: page and card surfaces, filled buttons with an outline, one accent primary button per page,
        # focus rings, and the system's light or dark theme (title bar included).
        self.t = theme.apply(root)
        root.configure(background=self.t["page"])
        theme.dark_title_bar(root)
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

    def _card(self, parent, title: str | None = None, pady=(0, 10), **grid):
        """A card as the tray draws them: a 1 px border around the card surface. Returns the frame to fill."""
        outer = self.tk.Frame(parent, bg=self.t["border"], padx=1, pady=1)
        outer.grid(sticky="nsew", pady=pady, **grid)
        inner = self.ttk.Frame(outer, style="Card.TFrame", padding=(GAP_L, GAP_M))
        inner.pack(fill="both", expand=True)
        inner.columnconfigure(0, weight=1)
        if title:
            self.ttk.Label(inner, text=title, style="Card.Title.TLabel").grid(sticky="w", pady=(0, GAP_S // 2))
        return inner

    def _header(self, parent, step: int, title: str, sub: str = ""):
        """Where the user is (the three steps, this one in the accent colour), the page's question, and what to do."""
        ttk, t = self.ttk, self.t
        strip = ttk.Frame(parent)
        strip.grid(sticky="w", pady=(0, GAP_M))
        for i, name in enumerate(WIZARD, start=1):
            if i > 1:
                ttk.Label(strip, text="›", foreground=t["muted"]).pack(side="left", padx=GAP_S)
            here = i == step
            ttk.Label(strip, text=f"{i}  {name}", foreground=t["accent"] if here else t["ink2"] if i < step else t["muted"],
                      font=(FONT, 9, "bold" if here else "normal")).pack(side="left")
        head = ttk.Label(parent, text=title, style="Head.TLabel")
        head.grid(sticky="w")
        sub_label = ttk.Label(parent, text=sub, style="HeadSub.TLabel", wraplength=WRAP, justify="left")
        sub_label.grid(sticky="w", pady=(GAP_S // 2, GAP_M))
        return head, sub_label

    def _buttons(self, primary: tuple[str, object], back=None, cancel: str = "Cancel"):
        """The footer: Back on the left; the page's one primary action (accent fill) and Cancel on the right."""
        ttk = self.ttk
        if back is not None:
            ttk.Button(self.footer, text="Back", command=back).pack(side="left")
        ttk.Button(self.footer, text=cancel, command=self.root.destroy).pack(side="right")
        btn = ttk.Button(self.footer, text=primary[0], command=primary[1], style="Accent.TButton", default="active")
        btn.pack(side="right", padx=(0, GAP_S))
        return btn

    # ------------------------------------------------------------ the choices, kept across both pages

    def _load(self):
        """Read this PC and the profile, and make the variables both pages edit, so Back and Next keep the choices."""
        tk = self.tk
        prof.write_profile()
        self.profile = prof.resolve_profile()
        d = self.d = install.defaults(self.profile)
        self.feature_vars = {fid: tk.BooleanVar(value=on) for fid, on in d["choice"].items()}
        # Remove: installed features that can come off again, and downloaded models the profile does not use.
        self.remove_vars = {fid: tk.BooleanVar(value=False) for fid in uninstall.REMOVABLE
                            if d["features"].get(fid) and (d["features"][fid].installed
                                                           or d["features"][fid].state in REPAIRABLE)}
        self.removals: dict[str, uninstall.Removal] = {}   # measured on first tick (a big folder takes seconds)
        self.measured_for: tuple = ()   # the ticked removals self.removals was (or is being) measured for
        try:
            unused = [m for m in uninstall.model_rows(self.profile) if m.downloaded and not m.use]
        except Exception:  # noqa: BLE001 - the list is optional; Ollama may be off and its folder unreadable
            unused = []
        self.model_vars = {m.name: (tk.BooleanVar(value=False), m) for m in unused}
        # More read aloud voices (Piper): ticked when the profile names them or they are downloaded already.
        from stacklib import dictation
        from stacklib.dictation import speak

        try:
            have = set(dictation.installed_packs(self.profile))
        except Exception:  # noqa: BLE001 - optional: the boxes start unticked
            have = set()
        named = set((self.profile.get("read_aloud") or {}).get("packs") or [])
        self.pack_vars = {k: tk.BooleanVar(value=k in have or k in named) for k in speak.PIPER_VOICES}
        self.option_vars = {k: tk.StringVar(value=v) for k, v in d["options"].items()}   # (section, key) -> value
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

    def packs(self) -> list[str]:
        """The read aloud voices ticked (config/installer.yaml voice_packs keys)."""
        return [k for k, v in getattr(self, "pack_vars", {}).items() if v.get()]

    def packs_changed(self):
        """A voice needs read aloud, and read aloud voice typing: ticking one ticks them; the estimates follow."""
        if self.packs():
            for fid in ("read_aloud", *features.BY_ID["read_aloud"].requires):
                if fid in self.feature_vars and not features.locked(fid, self.d["features"]):
                    self.feature_vars[fid].set(True)
                    if fid in self.remove_vars:
                        self.remove_vars[fid].set(False)
            self._mark_removals()
        self.option_changed()
        self.show_detail("read_aloud")

    def chosen(self) -> set[str]:
        return {fid for fid, v in self.feature_vars.items() if v.get()} - self.to_remove()

    def to_remove(self) -> set[str]:
        """Features ticked for removal (a feature that runs inside one goes with it)."""
        out = {fid for fid, v in getattr(self, "remove_vars", {}).items() if v.get()}
        return out | {dep for fid in out for dep in features.dependents(fid) if dep in getattr(self, "remove_vars", {})}

    def models_to_delete(self) -> list[str]:
        """Models ticked for deletion, less any that the chosen chat model now names."""
        keep = {self.options().get(("models", "primary")), self.options().get(("models", "small"))}
        return [name for name, (v, _m) in getattr(self, "model_vars", {}).items() if v.get() and name not in keep]

    def options(self) -> dict[tuple[str, str], str]:
        return {k: v.get() for k, v in self.option_vars.items()}

    def option_changed(self, _event=None):
        """A model or setting changed: estimate again with it, as if it were in the profile already."""
        d = self.d
        planned = features.with_options(self.profile, self.options())
        planned["read_aloud"] = {**(planned.get("read_aloud") or {}), "packs": self.packs()}
        d["estimates"] = features.estimates(planned, d["hardware"])
        d["models"] = features.models_to_pull(planned)
        d["models_gb"] = d["estimates"]["models"].disk_gb
        for fid, labels in self.cell_labels.items():
            values = features.cells(d["estimates"][fid], d["hardware"])
            for key, label in labels.items():
                label.configure(text=values[key])
        self.update_summary()
        if _event is not None:
            self.show_detail(self.option_owner.get(str(_event.widget), features.FEATURES[0].id))

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
        self.behind = self.ttk.Label(parent, text="", foreground=self.t["warn"], wraplength=WRAP)
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
        t = self.t
        self._header(f, 1, "Which features do you want?",
                     "The required parts are always installed, and installed features stay unless you tick Remove. "
                     "Tick the others you want; you can add or remove features later from the tray's Features card. "
                     "Settings in the tray turns a feature off without removing it.")
        self._behind_label(f)

        table = self._card(f)
        ttk.Label(table, text=f"This PC: {d['hardware'].describe()}. Each row is what that feature costs on its own; "
                  "Your choice adds up the ones you tick.", style="Card.Muted.TLabel", wraplength=WRAP - 40,
                  justify="left").grid(row=1, column=0, columnspan=3 + len(COLUMNS), sticky="w", pady=(0, GAP_M))
        table.columnconfigure(0, weight=1)
        # Room for the longest status up front, so ticking Remove ("Will be removed") does not squeeze the names.
        from tkinter import font as tkfont   # tkinter is imported in main(), where a missing Tk is reported

        font = tkfont.Font(root=self.root, family=FONT, size=10)
        table.columnconfigure(1, minsize=14 + max(font.measure(x) for x in ("Will be removed", "Not installed")))
        for c, head in enumerate(("Feature", "Status", *(title for _key, title in COLUMNS), "Remove")):
            ttk.Label(table, text=head, style="Card.Head.TLabel").grid(
                row=2, column=c, sticky="w" if c < 2 else "e", padx=(0 if c == 0 else 14, 0), pady=(0, 4))
        self.status_labels = {}
        first = None
        self.feature_boxes, self.cell_labels, self.option_boxes, self.option_owner = {}, {}, {}, {}
        self.listed: list[str] = []
        r = 2
        span = 3 + len(COLUMNS)
        for feat in features.FEATURES:
            if not feat.offered and not features.present(feat.id, d["features"]):
                continue   # no longer offered, and nothing of it on this PC: not listed at all
            self.listed.append(feat.id)
            r += 1   # a hairline between features, so each one's option line reads as part of it
            self.tk.Frame(table, height=1, bg=t["grid"]).grid(row=r, column=0, columnspan=span, sticky="ew", pady=1)
            r += 1
            st, is_locked = d["features"][feat.id], features.locked(feat.id, d["features"])
            box = self.feature_boxes[feat.id] = ttk.Checkbutton(
                table, text=feat.title, command=lambda fid=feat.id: self.feature_ticked(fid),
                variable=self.feature_vars[feat.id])
            if is_locked or not feat.offered:
                box.state(["disabled"])   # required, or installed and on (Settings turns it off), or remove-only
            elif first is None:
                first = feat.id
            box.grid(row=r, column=0, sticky="w", pady=2)
            text, key = status_text(feat, st, is_locked)
            row = [box, ttk.Label(table, text=text, style="Card.TLabel", foreground=t[key])]
            row[1].grid(row=r, column=1, sticky="w", padx=(14, 0))
            self.status_labels[feat.id] = (row[1], text, t[key])
            values = features.cells(d["estimates"][feat.id], d["hardware"])
            self.cell_labels[feat.id] = {}
            for c, (key, _title) in enumerate(COLUMNS, start=2):
                row.append(ttk.Label(table, text=values[key], style="Card.TLabel"))
                row[-1].grid(row=r, column=c, sticky="e", padx=(14, 0))
                self.cell_labels[feat.id][key] = row[-1]
            if feat.id in self.remove_vars:   # installed: a box to take it off again
                rm = ttk.Checkbutton(table, variable=self.remove_vars[feat.id],
                                     command=lambda fid=feat.id: self.remove_ticked(fid))
                rm.grid(row=r, column=2 + len(COLUMNS), sticky="e", padx=(14, 0))
                rm.bind("<FocusIn>", lambda _e, fid=feat.id: self.show_detail(fid), add="+")
                row.append(rm)
            for w in row:   # the box below explains the row under the pointer, or the one with keyboard focus
                w.bind("<Enter>", lambda _e, fid=feat.id: self.show_detail(fid), add="+")
            box.bind("<FocusIn>", lambda _e, fid=feat.id: self.show_detail(fid), add="+")
            if feat.id in features.OPTIONS:   # its models and first settings, on a line of their own
                r += 1
                line = ttk.Frame(table, style="Card.TFrame")
                line.grid(row=r, column=0, columnspan=span - 1, sticky="w", padx=(28, 0), pady=(0, 4))
                for opt, fn in features.OPTIONS[feat.id]:
                    choices = fn(self.profile)
                    names = dict(choices)
                    var = self.option_vars[(opt.section, opt.key)]
                    shown = self.tk.StringVar(value=names.get(var.get(), var.get()))
                    ttk.Label(line, text=f"{opt.label}:", style="Card.Sub.TLabel").pack(side="left", padx=(0, 4))
                    combo = ttk.Combobox(line, textvariable=shown, state="readonly", width=max(len(n) for n in names.values()) + 1,
                                         values=[n for _v, n in choices])

                    def picked(event, var=var, shown=shown, back={n: v for v, n in choices}):
                        var.set(back.get(shown.get(), shown.get()))
                        self.option_changed(event)
                    combo.bind("<<ComboboxSelected>>", picked)
                    combo.bind("<FocusIn>", lambda _e, fid=feat.id: self.show_detail(fid), add="+")
                    combo.bind("<MouseWheel>", lambda e: (self._wheel(e), "break")[1])   # scroll the page, not the choice
                    combo.pack(side="left", padx=(0, 14))
                    self.option_boxes[(opt.section, opt.key)] = combo
                    self.option_owner[str(combo)] = feat.id
            if feat.id == "read_aloud" and self.pack_vars:   # more languages: Piper voices, three to a line
                from stacklib.dictation import speak

                r += 1
                grid = ttk.Frame(table, style="Card.TFrame")
                grid.grid(row=r, column=0, columnspan=3 + len(COLUMNS), sticky="w", padx=(28, 0), pady=(0, 2))
                ttk.Label(grid, text="More voices:", style="Card.Sub.TLabel").grid(row=0, column=0, sticky="nw",
                                                                                   padx=(0, 6))
                for i, (key, var) in enumerate(self.pack_vars.items()):
                    meta = speak.PIPER_VOICES[key]
                    who = " and ".join(str(x[0]) for x in (meta.get("speakers") or {}).values())
                    lang = speak.language_label(str(meta.get("language") or ""))
                    star = "*" if meta.get("lessac_base") else ""
                    box = ttk.Checkbutton(grid, text=f"{lang}: {who} ({meta.get('size_mb')} MB){star}", variable=var,
                                          command=self.packs_changed)
                    box.grid(row=i // 3, column=1 + i % 3, sticky="w", padx=(0, 14))
                    box.bind("<FocusIn>", lambda _e: self.show_detail("read_aloud"), add="+")
                r += 1
                ttk.Label(table, style="Card.Muted.TLabel", wraplength=WRAP - 60, justify="left",
                          text="* Piper voices fine-tuned from a voice whose training data is licensed for research "
                               "only; their own recordings are open (CC0, CC BY or CC BY-SA). They run on this PC's "
                               "CPU in read aloud's own environment.").grid(
                    row=r, column=0, columnspan=3 + len(COLUMNS), sticky="w", padx=(28, 0), pady=(0, 4))
            if feat.id == "models" and self.model_vars:   # downloaded models nothing uses: delete them?
                r += 1
                line = ttk.Frame(table, style="Card.TFrame")
                line.grid(row=r, column=0, columnspan=span, sticky="w", padx=(28, 0), pady=(0, 4))
                ttk.Label(line, text="Not used by the stack, delete:", style="Card.Sub.TLabel").pack(side="left", padx=(0, 4))
                for name, (var, m) in self.model_vars.items():
                    ttk.Checkbutton(line, text=f"{name} ({m.size_gb:.1f} GB)", variable=var,
                                    command=self.update_summary).pack(side="left", padx=(0, 14))

        # What the row under the pointer (or with the keyboard focus) is and costs: its name, one line on what it
        # does, then its state and its load one fact per line. Held at the tallest row's height, so the page does
        # not jump while the pointer moves down the table.
        # Side by side under the table, so both stay in view on a 1080-pixel screen: the row's detail on the left,
        # the choice's total on the right.
        below = ttk.Frame(f)
        below.grid(sticky="ew")
        below.columnconfigure((0, 1), weight=1, uniform="below")
        self.detail_box = self._card(below, pady=(0, 0), row=0, column=0, padx=(0, 5))
        self.detail_title = ttk.Label(self.detail_box, text="", style="Card.Title.TLabel")
        self.detail_title.grid(row=0, column=0, sticky="w")
        self.detail_lead = ttk.Label(self.detail_box, text="", style="Card.TLabel", wraplength=HALF, justify="left")
        self.detail_lead.grid(row=1, column=0, sticky="w", pady=(4, 6))
        self.detail = ttk.Label(self.detail_box, text="", style="Card.Sub.TLabel", wraplength=HALF, justify="left")
        self.detail.grid(row=2, column=0, sticky="nw")
        self.summary_card = self._card(below, "Your choice on this PC", pady=(0, 0), row=0, column=1, padx=(5, 0))
        self.summary_box = ttk.Frame(self.summary_card, style="Card.TFrame")
        self.summary_box.grid(sticky="ew")
        self.summary_box.columnconfigure(1, weight=1)
        self._buttons(("Next", self.show_folders))
        self.root.bind("<Return>", lambda e: self.show_folders())
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self._hold_detail_height()
        self.show_detail(first or features.FEATURES[0].id)
        self.update_summary()

    def _hold_detail_height(self):
        """Give the detail text the height of the longest feature's, measured once per page."""
        lead = body = 0
        for fid in self.listed:
            self.show_detail(fid)
            self.detail_box.update_idletasks()
            lead = max(lead, self.detail_lead.winfo_reqheight())
            body = max(body, self.detail.winfo_reqheight())
        self.detail_box.rowconfigure(1, minsize=lead + 10)   # + its pady
        self.detail_box.rowconfigure(2, minsize=body)

    def feature_ticked(self, fid: str):
        """Keep features with what they run inside: ticking read aloud ticks voice typing, and unticking voice typing
        unticks read aloud (a locked feature stays as it is). Ticking a feature takes back its Remove tick."""
        v = self.feature_vars
        if v[fid].get():
            for need in features.BY_ID[fid].requires:
                v[need].set(True)
                if need in self.remove_vars:
                    self.remove_vars[need].set(False)
            if fid in self.remove_vars:
                self.remove_vars[fid].set(False)
        else:
            for dep in features.dependents(fid):
                if not features.locked(dep, self.d["features"]):
                    v[dep].set(False)
        self._mark_removals()
        self.update_summary()

    def remove_ticked(self, fid: str):
        """A Remove box: the row says "Will be removed", what runs inside it goes too, and what the removal deletes is
        measured in the background for the detail box and the summary."""
        on = self.remove_vars[fid].get()
        for dep in features.dependents(fid):
            if dep in self.remove_vars and on:
                self.remove_vars[dep].set(True)
        if not on:
            for need in features.BY_ID[fid].requires:   # read aloud stays: voice typing must stay too
                if need in self.remove_vars:
                    self.remove_vars[need].set(False)
        self._mark_removals()
        self.show_detail(fid)
        self.update_summary()
        gone = sorted(self.to_remove())
        if gone and tuple(gone) != self.measured_for:
            self.measured_for = tuple(gone)
            done: list[dict] = []
            threading.Thread(target=lambda: done.append(self.measure(gone)), daemon=True).start()

            def check():   # Tk only on its own thread: poll for the thread's result
                if not done:
                    self.root.after(POLL_MS // 2, check)
                    return
                if self.measured_for == tuple(gone):
                    self.removals = done[0]
                    self.update_summary()
                    self.show_detail(fid)
            self.root.after(POLL_MS // 2, check)

    def measure(self, gone: list[str]) -> dict:
        """What removing each ticked feature deletes, planned in order, each as if the ones before it were gone: a
        Whisper model voice typing and recordings share goes with the second, and is counted there once."""
        status, out = dict(self.d["features"]), {}
        for f in install.removal_order(gone):
            try:
                out[f] = uninstall.plan(self.profile, f, status)
            except Exception as e:  # noqa: BLE001 - shown in the summary and the confirmation
                out[f] = uninstall.Removal(f, features.BY_ID[f].title, blocked=f"not checked: {e}")
            status[f] = features.Status(False, False, "Not installed", level="off")
        return out

    def _mark_removals(self):
        """The Status column of every row ticked for removal says so; the others say what they said."""
        gone = self.to_remove()
        for fid, (label, text, fg) in getattr(self, "status_labels", {}).items():
            if not self._alive(label):
                continue
            if fid in gone:
                label.configure(text="Will be removed", foreground=self.t["bad"])
                if fid in self.feature_vars:
                    self.feature_vars[fid].set(False)
            else:
                label.configure(text=text, foreground=fg)
                if fid in self.remove_vars and not self.feature_vars[fid].get():
                    self.feature_vars[fid].set(self.d["choice"].get(fid, False))   # back to its first tick

    def show_detail(self, fid: str):
        if not self._alive(getattr(self, "detail", None)):
            return
        feat, d = features.BY_ID[fid], self.d
        st = d["features"][fid]
        lines = []
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
        # One fact per line (GPU, CPU, Memory, When, Disk) instead of one paragraph.
        lines.append(re.sub(r" (?=(?:GPU|CPU|Memory|When|Disk): )", "\n", features.detail_text(d["estimates"][fid])))
        if fid in self.to_remove():
            r = self.removals.get(fid)
            lines = ["Ticked for removal.", r.text() if r else "Measuring what it deletes..."]
        self.detail_title.configure(text=feat.title)
        self.detail_lead.configure(text=feat.summary)
        self.detail.configure(text=uninstall.short_text("\n".join(lines)))

    def update_summary(self):
        if not self._alive(self.summary_box):
            return
        ttk, d = self.ttk, self.d
        for child in self.summary_box.winfo_children():
            child.destroy()
        installed = {fid for fid, s in d["features"].items() if s.installed} - self.to_remove()
        findings = features.assess(self.chosen(), d["estimates"], d["hardware"], installed)
        gone = self.to_remove()
        if gone:
            measured = [self.removals.get(f) for f in gone]
            # Each folder once: voice typing's plan and read aloud's can both name Kokoro's.
            size = sum({i.path or f"{r.fid}:{i.what}": i.size_gb or 0.0 for r in measured if r for i in r.deletes}.values())
            names = ", ".join(x.short for x in features.FEATURES if x.id in gone)
            blocked = [r.blocked for r in measured if r and r.blocked]
            text = (f"Removes {names}" + (f": frees about {size:.1f} GB" if all(measured) and size else
                                          ": measuring what it deletes" if not all(measured) else "")
                    + ". What you made with them (chats, images, transcripts, settings) stays.")
            findings.insert(0, features.Finding("bad" if blocked else "warn", text + (f" {' '.join(blocked)}" if blocked else "")))
        models = self.models_to_delete()
        if models:
            gb = sum(self.model_vars[n][1].size_gb for n in models)
            findings.insert(0, features.Finding("warn", f"Deletes {', '.join(models)}: frees about {gb:.1f} GB. You can "
                                                        "download a model again later."))
        t = self.t
        for i, finding in enumerate(findings):
            sym, key = FINDING.get(finding.level, FINDING["ok"])
            ttk.Label(self.summary_box, text=sym, style="Card.TLabel", foreground=t[key], width=2, font=(FONT, 11)).grid(
                row=i, column=0, sticky="nw")
            text = ttk.Label(self.summary_box, text=finding.text, style="Card.TLabel", wraplength=HALF - 24, justify="left")
            if finding.level != "ok":
                text.configure(foreground=t[key])
            text.grid(row=i, column=1, sticky="w", pady=1)

    # ------------------------------------------------------------ page 2: folders and options

    def show_folders(self):
        ttk, d = self.ttk, self.d
        chosen = self.chosen()
        f = self._page()
        self._header(f, 2, "Where should Agent Stack put its files?",
                     "Choose the folders, then Install. Setup runs in the background; you can close this window while "
                     "it works.")
        self._behind_label(f)
        self.store_msg = self._folder(f, "Models (Ollama)", "Downloaded models live here. Needs the most space; "
                                      "a fast internal drive loads models quicker than a USB one.", self.store, d["model_note"])
        tools = ", ".join(name for fid, name in TOOL_NAMES.items() if fid in install.chosen_with_required(chosen))
        self.tools_msg = self._folder(f, f"Python tools ({tools})",
                                      "Each tool gets its own Python environment here. Keep the path short.", self.tools)
        self.media_msg = None
        if install.needs_media(chosen):
            installed = d["features"]["images"].installed
            self.media_msg = self._folder(f, "Media (ComfyUI and its models)",
                                          "ComfyUI with the image model goes here. Agent sessions and media tools may "
                                          "use only this folder.", self.media_root,
                                          "Installed already: setup checks and updates it." if installed else "")

        opts = self._card(f, "Options")
        ttk.Checkbutton(opts, variable=self.pull, command=self.validate,
                        text=f"Download models now: {', '.join(d['models'])} (about {d['models_gb']:.1f} GB)").grid(sticky="w")
        self.move_box = None
        if d["move_from"]:   # shown by validate() only while the models folder differs from where they are
            self.move_box = ttk.Checkbutton(opts, variable=self.move, command=self.validate,
                                            text=f"Move the {d['move_gb']:.1f} GB of models already in {d['move_from']}")
            self.move_box.grid(sticky="w")
        if d["ollama_missing"]:
            ttk.Checkbutton(opts, variable=self.get_ollama, command=self.validate, text="Install Ollama with winget (it is not installed; "
                            "accepts the Ollama package agreement)").grid(sticky="w")
        ttk.Checkbutton(opts, variable=self.disks, text="Check how fast each drive is and warn about slow ones "
                        "(writes a 256 MB test file per drive)").grid(sticky="w")
        self.hf_box = ttk.Checkbutton(opts, variable=self.hf)
        self.hf_box.grid(sticky="w")
        ttk.Checkbutton(opts, variable=self.start, command=self.validate, text="Start the stack when setup finishes (tray app)").grid(sticky="w")

        # What pressing the button will do, in one place, before anything starts.
        plan = self._card(f, "What happens next", pady=(0, 0))
        self.plan_label = ttk.Label(plan, text="", style="Card.TLabel", wraplength=WRAP - 40, justify="left")
        self.plan_label.grid(sticky="w")
        self.error = ttk.Label(f, text="", foreground=self.t["bad"], wraplength=WRAP)
        self.error.grid(sticky="w", pady=(GAP_S, 0))
        changes = bool(self.to_remove() or self.models_to_delete())
        self.install_btn = self._buttons(("Apply changes" if changes else "Install", self.on_install), back=self.show_features)
        self.root.bind("<Return>", lambda e: self.on_install())
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.validate()

    def plan_text(self) -> str:
        """One line per thing Install does, from the choice on page 1 and the options on page 2."""
        d, chosen, gone = self.d, self.chosen(), self.to_remove()
        new = [x.short for x in features.FEATURES if x.id in chosen and not d["features"][x.id].installed]
        lines = []
        if gone:
            lines.append("Removes " + ", ".join(x.short for x in features.FEATURES if x.id in gone)
                         + " (what you made with them stays).")
        if self.models_to_delete():
            lines.append("Deletes the models " + ", ".join(self.models_to_delete()) + ".")
        if d["ollama_missing"] and self.get_ollama.get():
            lines.append("Installs Ollama with winget.")
        lines.append(f"Installs {', '.join(new)}." if new else "Checks the installed features and repairs what is missing.")
        if self._moving():
            lines.append(f"Moves the models in {d['move_from']} to the models folder.")
        if self.pull.get() and d["models"]:
            lines.append(f"Downloads what is missing of {', '.join(d['models'])} (up to {d['models_gb']:.1f} GB).")
        lines.append("Starts the stack and the tray when it finishes." if self.start.get()
                     else "Leaves the stack stopped: start it from Agent Stack in the Start menu.")
        return "\n".join(f"•  {line}" for line in lines)

    def _folder(self, parent, title, hint, var, note=""):
        ttk = self.ttk
        box = self._card(parent, title)
        ttk.Label(box, text=hint, style="Card.Sub.TLabel", wraplength=WRAP - 40, justify="left").grid(
            row=1, column=0, columnspan=2, sticky="w")
        entry = ttk.Entry(box, textvariable=var)
        entry.grid(row=2, column=0, sticky="ew", pady=(GAP_S, 0))
        ttk.Button(box, text="Browse...", command=lambda: self.browse(var, title)).grid(row=2, column=1, padx=(GAP_S, 0),
                                                                                          pady=(GAP_S, 0))
        msg = ttk.Label(box, text="", style="Card.TLabel", wraplength=WRAP - 40, justify="left")
        msg.grid(row=3, column=0, columnspan=2, sticky="w", pady=(GAP_S // 2, 0))
        if note:
            ttk.Label(box, text=note, style="Card.Muted.TLabel", wraplength=WRAP - 40, justify="left").grid(
                row=4, column=0, columnspan=2, sticky="w", pady=(2, 0))
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
            chk = install.check_dir(var.get(), need, models=var is self.store)
            # A mark as well as the colour, so the result does not rest on colour alone.
            label.configure(text=f"{'✓' if chk.ok else '✗'}  {chk.message}", foreground=self.t["good" if chk.ok else "bad"])
            ok &= chk.ok
        self.install_btn.state(["!disabled"] if ok else ["disabled"])
        if self._alive(getattr(self, "plan_label", None)):
            self.plan_label.configure(text=self.plan_text() if ok else "Fix the folder marked ✗ above to continue.")
        return ok

    def on_install(self, confirmed: bool = False):
        if not self.validate():
            return
        gone, models = sorted(self.to_remove()), self.models_to_delete()
        if gone and (tuple(gone) != self.measured_for or any(f not in self.removals for f in gone)):
            self.root.configure(cursor="watch")   # not measured yet: measure now, so the question lists everything
            self.root.update_idletasks()
            try:
                self.removals, self.measured_for = self.measure(gone), tuple(gone)
            finally:
                self.root.configure(cursor="")
        blocked = [r.blocked for f in gone for r in [self.removals.get(f)] if r and r.blocked]
        if blocked:
            self.error.configure(text=" ".join(blocked))
            return
        if (gone or models) and not confirmed:
            self.confirm_removals(gone, models)
            return
        chosen = self.chosen()
        store = str(Path(self.store.get().strip()).expanduser())
        tools = str(Path(self.tools.get().strip()).expanduser())
        media_root = str(Path(self.media_root.get().strip()).expanduser()) if install.needs_media(chosen) else ""
        try:
            for path in (store, tools):
                Path(path).mkdir(parents=True, exist_ok=True)
            install.save_paths(self.profile, store)
            install.save_features(self.profile, chosen, media_root, self.d["features"], self.options(), remove=gone,
                                  packs=self.packs())
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
                remove=gone,
                remove_models=models,
                targets=sorted(set(gone) | (chosen - {f for f, s in self.d["features"].items() if s.installed})
                               | ({"models"} if models else set())),
                **install.feature_plan(chosen, self.d["features"]),
            )
            install.spawn_worker(plan)
        except (OSError, ValueError, RuntimeError) as e:
            self.error.configure(text=f"Could not start setup: {e}")
            return
        self.root.unbind("<Return>")
        self.show_progress()

    def confirm_removals(self, gone: list[str], models: list[str]):
        """Ask before anything is deleted: what goes, how much, what stays. The safe button has the focus; the
        destructive one is outlined in the danger colour, as in the tray."""
        tk, ttk = self.tk, self.ttk
        d = tk.Toplevel(self.root)
        d.title("Remove features?")
        d.transient(self.root)
        d.resizable(False, False)
        d.configure(background=self.t["card"])
        theme.dark_title_bar(d)
        f = ttk.Frame(d, style="Card.TFrame", padding=GAP_XL)
        f.pack(fill="both", expand=True)
        names = [features.BY_ID[x].title for x in gone] + models
        ttk.Label(f, text=f"Remove {', '.join(names)}?", style="Card.Title.TLabel", font=(FONT, 12, "bold"),
                  wraplength=600).pack(anchor="w")
        parts = [self.removals[x].text() if x in self.removals else features.BY_ID[x].title for x in gone]
        if models:
            parts.append("Deletes the models " + ", ".join(models) + "; you can download them again later.")
        ttk.Label(f, text=uninstall.short_text("\n\n".join(parts)), style="Card.TLabel", wraplength=600,
                  justify="left").pack(anchor="w", pady=(GAP_S, GAP_L))
        buttons = ttk.Frame(f, style="Card.TFrame")
        buttons.pack(fill="x")

        def close():
            d.grab_release()
            d.destroy()

        def go():
            close()
            self.on_install(confirmed=True)

        back = ttk.Button(buttons, text="Go back", command=close)
        back.pack(side="right")
        ttk.Button(buttons, text="Remove and apply", style="Danger.TButton", command=go).pack(side="right", padx=(0, GAP_S))
        d.bind("<Escape>", lambda _e: close())
        d.bind("<Return>", lambda e: e.widget.invoke() if hasattr(e.widget, "invoke") else close())
        d.protocol("WM_DELETE_WINDOW", close)
        d.update_idletasks()
        d.geometry(f"+{self.root.winfo_rootx() + 80}+{self.root.winfo_rooty() + 80}")
        d.grab_set()
        back.focus_set()

    # ------------------------------------------------------------ page 3: progress

    def show_progress(self):
        tk, ttk, t = self.tk, self.ttk, self.t
        f = self._page(scroll=False)   # the log box takes the spare height instead
        self.heading, self.subheading = self._header(
            f, 3, install.summary({"status": "running"}),
            "You can close this window; setup keeps running. Open the installer again to see where it is.")
        card = self._card(f)
        steps = ttk.Frame(card, style="Card.TFrame")
        steps.grid(sticky="ew")
        steps.columnconfigure(2, weight=1)
        self.step_rows = {}
        self.step_started: dict[str, float] = {}   # when this window first saw each step running (for its elapsed time)
        # The steps this run has (removals first, or the few the tray asked for); all of STEPS before the state exists.
        step_list = [(s["id"], s["title"], None) for s in install.read_state().get("steps") or []] or install.STEPS
        for i, (sid, title, _) in enumerate(step_list):
            sym, key = MARK["pending"]
            mark = ttk.Label(steps, text=sym, style="Card.TLabel", foreground=t[key], width=2, font=(FONT, 11))
            mark.grid(row=i, column=0, sticky="nw")
            name = ttk.Label(steps, text=title, style="Card.TLabel")
            name.grid(row=i, column=1, sticky="nw", padx=(0, GAP_M), pady=1)
            detail = ttk.Label(steps, text="", style="Card.Sub.TLabel", wraplength=480, justify="left")
            detail.grid(row=i, column=2, sticky="nw", pady=1)
            self.step_rows[sid] = (mark, detail, name)
        # One bar for the whole run (finished steps plus the running step's share), and a line that names the step,
        # its percentage when it reports one, else how long it has been running, so a long step still shows life.
        self.bar = ttk.Progressbar(card, mode="determinate", maximum=1.0)
        self.bar.grid(sticky="ew", pady=(GAP_M, GAP_S // 2))
        self.bar_text = ttk.Label(card, text="", style="Card.Muted.TLabel")
        self.bar_text.grid(sticky="w")
        f.rowconfigure(4, weight=1)
        logcard = self._card(f, pady=(0, 0))
        logcard.master.grid_configure(row=4, sticky="nsew")
        logcard.rowconfigure(1, weight=1)
        head = ttk.Frame(logcard, style="Card.TFrame")
        head.grid(row=0, sticky="ew", pady=(0, GAP_S))
        ttk.Label(head, text="Log", style="Card.Title.TLabel").pack(side="left")
        ttk.Button(head, text="Open log file", command=lambda: open_path(install.LOG_FILE)).pack(side="right")
        logbox = ttk.Frame(logcard, style="Card.TFrame")
        logbox.grid(row=1, sticky="nsew")
        logbox.columnconfigure(0, weight=1)
        logbox.rowconfigure(0, weight=1)
        self.log = tk.Text(logbox, height=10, wrap="none", font=("Consolas", 9), state="disabled", relief="flat",
                           background=t["page"], foreground=t["ink"], borderwidth=0, highlightthickness=1,
                           highlightbackground=t["border"], highlightcolor=t["accent"], padx=6, pady=4)
        self.log.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(logbox, command=self.log.yview)
        sb.grid(row=0, column=1, sticky="ns")
        def yset(first, last):   # the scrollbar only while the log is longer than the box
            if float(first) <= 0 and float(last) >= 1:
                sb.grid_remove()
            else:
                sb.grid()
            sb.set(first, last)
        self.log.configure(yscrollcommand=yset)
        self.footer = ttk.Frame(f)
        self.footer.grid(row=5, sticky="ew", pady=(GAP_M, 0))
        self.close_btn = ttk.Button(self.footer, text="Close", command=self.root.destroy)
        self.close_btn.pack(side="right")
        self.retry_btn = ttk.Button(self.footer, text="Change choices and run again",
                                    command=lambda: self.show_features(reload=True))
        self.open_btn = None
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.root.unbind("<Return>")
        self._log_size = -1
        self.poll()

    def poll(self):
        if self.body is None or not self.body.winfo_exists() or not self.step_rows:
            return
        t = self.t
        state = install.read_state()
        status = state.get("status", "running")
        self.heading.configure(text=install.summary(state) if state else "Starting setup...")
        running, steps = None, state.get("steps", [])
        for s in steps:
            mark, detail, name = self.step_rows.get(s["id"], (None, None, None))
            if mark is None:
                continue
            sym, key = MARK.get(s["status"], MARK["pending"])
            mark.configure(text=sym, foreground=t[key])
            name.configure(style="Card.Name.TLabel" if s["status"] == "running" else "Card.TLabel")
            word = {"skipped": "Skipped: ", "warning": "Warning: ", "failed": "Failed: "}.get(s["status"], "")
            detail.configure(text=word + s["detail"] if s["detail"] else word.rstrip(": "),
                             foreground=t[{"failed": "bad", "warning": "warn"}.get(s["status"], "ink2")])
            if s["status"] == "running":
                running = s
                self.step_started.setdefault(s["id"], time.monotonic())
        finished = sum(s["status"] in ("done", "skipped", "warning", "failed") for s in steps)
        total = len(steps) or len(self.step_rows)
        self.bar["value"] = 1.0 if status in ("done", "warnings") else (
            finished + ((running or {}).get("fraction") or 0.0)) / max(total, 1)
        if running:
            n = [s["id"] for s in steps].index(running["id"]) + 1
            if running.get("fraction") is not None:
                how = f"{running['fraction'] * 100:.0f}%"
            else:
                secs = int(time.monotonic() - self.step_started[running["id"]])
                how = f"working, {secs // 60} min {secs % 60:02d} s" if secs >= 60 else f"working, {secs} s"
            self.bar_text.configure(text=f"Step {n} of {total}: {running['title']}  ·  {how}")
        elif status == "running" or not state:
            self.bar_text.configure(text="Starting...")
        else:
            problems = sum(s["status"] == "failed" for s in steps)
            self.bar_text.configure(text=f"{finished} of {total} steps ran" + (f", {problems} failed" if problems else ""))
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
            self._finished_buttons(status)

    def _finished_buttons(self, status: str):
        """After the run: one primary action. Open the chat when setup worked and Open WebUI is on; run again when it
        did not. Close stays a plain button."""
        if self.retry_btn.winfo_manager():
            return
        url = self._chat_url() if status in ("done", "warnings") else ""
        retry_first = status in ("failed", "interrupted")
        self.retry_btn.configure(style="Accent.TButton" if retry_first else "TButton")
        self.retry_btn.pack(side="right", padx=(0, GAP_S))
        if url:
            import webbrowser

            self.open_btn = self.ttk.Button(self.footer, text="Open chat", style="Accent.TButton",
                                            command=lambda: webbrowser.open(url))
            self.open_btn.pack(side="right", padx=(0, GAP_S))
            self.open_btn.focus_set()
        elif retry_first:
            self.retry_btn.focus_set()

    @staticmethod
    def _chat_url() -> str:
        try:
            p = prof.resolve_profile()
        except (OSError, ValueError):
            return ""
        return f"http://127.0.0.1:{p['ports']['open_webui']}" if p["services"].get("open_webui") == "native" else ""

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
