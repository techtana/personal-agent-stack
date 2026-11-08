"""The history windows. Refine history: the entries the refine log still keeps (refine.keep_minutes), newest first, with
the text before and after side by side (removed words struck through in red, added words underlined in green). Copy
either version, or select the refined text in its app and click Revert to put the original back. Voice typing history
(VoiceHistoryWindow): what you dictated in the last dictation.keep_minutes, as Whisper heard it and as it was typed;
copy either, or type it again into the app you came from.

A normal window that takes the keyboard focus (unlike the buttons): Up and Down move through the list, Tab reaches the
buttons, Esc closes. It reads the log again whenever it comes back to the front, so a revert shows up at once.
"""
from __future__ import annotations

import difflib
import os
import re
import subprocess
import tkinter as tk
from pathlib import Path

from .refinelog import REVERTIBLE

FONT = "Segoe UI" if os.name == "nt" else "TkDefaultFont"
MONO = "Cascadia Mono" if os.name == "nt" else "TkFixedFont"
# Same dark palette as the button's bubble; every text colour passes 4.5:1 on its background (WCAG AA).
BG, FIELD, FG, MUTED, BORDER, ACCENT = "#1f1f1f", "#2b2b2b", "#f3f3f3", "#b4b4b4", "#3d3d3d", "#4ca0f0"
SELECT_BG, DEL_BG, INS_BG = "#0f6cbd", "#5c2b29", "#1e4620"
STATUS = {"replaced": "replaced", "copied": "on clipboard", "rejected": "rejected", "unchanged": "no change",
          "cancelled": "cancelled", "failed": "failed", "skipped": "not replaced"}
_TOKEN = re.compile(r"\s+|\w+|[^\w\s]")
VOICE_STATUS = {"inserted": "typed", "copied": "on clipboard", "failed": "failed"}
TICK_MS = 30_000   # how often an open window re-reads the log (entries expire after refine.keep_minutes)


def diff_spans(before: str, after: str) -> tuple[list[tuple[str, bool]], list[tuple[str, bool]]]:
    """(text, changed) pieces of both texts, compared word by word."""
    a, b = _TOKEN.findall(before or ""), _TOKEN.findall(after or "")
    left: list[tuple[str, bool]] = []
    right: list[tuple[str, bool]] = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        changed = op != "equal"
        if i2 > i1:
            left.append(("".join(a[i1:i2]), changed))
        if j2 > j1:
            right.append(("".join(b[j1:j2]), changed))
    return left, right


def row_text(e: dict, reverted: set) -> str:
    when = str(e.get("time") or "")[5:16].replace("T", " ")
    if e.get("kind") == "revert":
        what, status = "Revert", "original back" if e.get("status") == "replaced" else STATUS.get(e.get("status"), "")
    else:
        what = e.get("style_name") or e.get("style") or "?"
        status = STATUS.get(e.get("status"), e.get("status") or "")
        if e.get("id") in reverted:
            status += ", reverted"
    app = (e.get("app") or "").removesuffix(".exe")
    words = " ".join(str(e.get("before") or "").split())
    return f"{when}   {what[:22]:<22}  {app[:12]:<12}  {status:<22}  {words[:70]}"


class HistoryWindow:
    _open: "HistoryWindow | None" = None   # one window per class
    TITLE = "Refine history"

    def __init__(self, master: tk.Misc, app) -> None:
        cls = type(self)
        old = cls._open
        if old is not None and old.alive():
            old.reload()
            old.win.deiconify()
            old.win.lift()
            old.win.focus_force()
            return
        cls._open = self
        self.app = app
        self.entries: list[dict] = []
        self.mtime = 0.0
        scale = max(1.0, master.winfo_fpixels("1i") / 96.0)
        pad = int(10 * scale)

        self.win = tk.Toplevel(master, bg=BG)
        self.win.title(self.TITLE)
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        w, h = min(int(1040 * scale), sw - 40), min(int(660 * scale), sh - 80)
        self.win.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 3}")
        self.win.minsize(int(640 * scale), int(420 * scale))
        self.win.attributes("-topmost", True)
        self.win.after(400, lambda: self.win.attributes("-topmost", False))  # in front once, then a normal window

        top = tk.Frame(self.win, bg=BG, padx=pad, pady=pad)
        top.pack(fill="both", expand=True)
        tk.Label(top, text=self.TITLE, bg=BG, fg=FG, font=(FONT, 11, "bold"), anchor="w").pack(fill="x")
        tk.Label(top, text=self.intro(),
                 bg=BG, fg=MUTED, font=(FONT, 9), anchor="w", justify="left", wraplength=w - 3 * pad).pack(fill="x", pady=(2, 8))

        box = tk.Frame(top, bg=BG)
        box.pack(fill="x")
        self.list = tk.Listbox(box, height=9, activestyle="none", exportselection=False, font=(MONO, 9),
                               relief="flat", bg=FIELD, fg=FG, selectbackground=SELECT_BG, selectforeground="#ffffff",
                               highlightthickness=2, highlightbackground=BORDER, highlightcolor=ACCENT)
        bar = tk.Scrollbar(box, orient="vertical", command=self.list.yview)
        self.list.configure(yscrollcommand=bar.set)
        self.list.pack(side="left", fill="x", expand=True)
        bar.pack(side="right", fill="y")

        panes = tk.Frame(top, bg=BG)
        panes.pack(fill="both", expand=True, pady=(pad, 0))
        panes.columnconfigure(0, weight=1, uniform="p")
        panes.columnconfigure(1, weight=1, uniform="p")
        panes.rowconfigure(1, weight=1)
        self.before_label = tk.Label(panes, text="Before", bg=BG, fg=FG, font=(FONT, 9, "bold"), anchor="w")
        self.before_label.grid(row=0, column=0, sticky="w")
        self.after_label = tk.Label(panes, text="After", bg=BG, fg=FG, font=(FONT, 9, "bold"), anchor="w")
        self.after_label.grid(row=0, column=1, sticky="w", padx=(pad, 0))
        self.before = self._text(panes)
        self.before.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        self.after = self._text(panes)
        self.after.grid(row=1, column=1, sticky="nsew", padx=(pad, 0), pady=(4, 0))
        self.before.tag_configure("chg", background=DEL_BG, overstrike=True)
        self.after.tag_configure("chg", background=INS_BG, underline=True)

        self.detail = tk.Label(top, text="", bg=BG, fg=MUTED, font=(FONT, 9), anchor="w", justify="left",
                               wraplength=w - 3 * pad)
        self.detail.pack(fill="x", pady=(6, 0))
        buttons = tk.Frame(top, bg=BG)
        buttons.pack(fill="x", pady=(8, 0))
        self.make_buttons(buttons)
        self._button(buttons, "Open log folder", self._open_folder)
        self._button(buttons, "Close", self.close, side="right")

        self.list.bind("<<ListboxSelect>>", lambda _e: self._show())
        self.win.bind("<Escape>", lambda _e: self.close())
        # Coming back to the window focuses a child widget, not the window itself; reload() only stats the file
        # unless the log changed.
        self.win.bind("<FocusIn>", lambda _e: self.reload())
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        self.reload()
        self.win.focus_force()
        self.list.focus_set()
        self.win.after(TICK_MS, self._tick)

    # ---------------------------------------------------------------- what differs between the two windows

    def log(self):
        return self.app.refine_log

    def intro(self) -> str:
        return (f"Suggestions are kept for {self.app.refine_keep_text()} in {self.log().path}, then deleted. To put an "
                "original back, select the refined text in its app, pick the entry here and click Revert in the app.")

    def empty_text(self) -> str:
        return (f"  Nothing refined in the last {self.app.refine_keep_text()}. Select text in any app and click the "
                "refine button.")

    def row(self, e: dict, entries: list[dict]) -> str:
        return row_text(e, self.log().reverted_ids(entries))

    def make_buttons(self, frame) -> None:
        self.copy_before = self._button(frame, "Copy original", lambda: self._copy("before"))
        self.copy_after = self._button(frame, "Copy suggestion", lambda: self._copy("after"))
        self.revert_button = self._button(frame, "Revert in the app", self._revert)

    def update_buttons(self, e: dict | None) -> None:
        can_revert = bool(e and e.get("kind") == "refine" and e.get("status") in REVERTIBLE)
        self.revert_button.configure(state="normal" if can_revert else "disabled")

    def labels(self, e: dict) -> tuple[str, str]:
        if e.get("kind") == "revert":
            return "Selected (refined text)", "Put back (original)"
        return "Before (your text)", "After (suggestion)" if e.get("status") != "replaced" else "After (pasted)"

    def copied_text(self, field: str) -> str:
        return ("Original" if field == "before" else "Suggestion") + " copied to the clipboard."

    # ---------------------------------------------------------------- widgets

    def _text(self, master) -> tk.Text:
        t = tk.Text(master, wrap="word", font=(FONT, 10), relief="flat", bg=FIELD, fg=FG, insertbackground=FG,
                    padx=8, pady=6, highlightthickness=2, highlightbackground=BORDER, highlightcolor=ACCENT,
                    height=8, cursor="arrow")
        t.bind("<Key>", lambda e: None if (e.state & 0x4 and e.keysym.lower() in ("c", "a")) or e.keysym in (
            "Tab", "Up", "Down", "Left", "Right", "Prior", "Next", "Home", "End") else "break")  # read-only, copyable
        return t

    def _button(self, master, text: str, command, side: str = "left") -> tk.Button:
        b = tk.Button(master, text=text, command=command, font=(FONT, 9), relief="flat", bg="#3a3a3a", fg=FG,
                      activebackground="#4a4a4a", activeforeground=FG, padx=12, pady=4, highlightthickness=2,
                      highlightbackground=BG, highlightcolor=ACCENT, disabledforeground="#8a8a8a", cursor="hand2")
        b.bind("<Return>", lambda _e: command())
        b.pack(side=side, padx=(0, 8) if side == "left" else (8, 0))
        return b

    # ---------------------------------------------------------------- data

    def alive(self) -> bool:
        try:
            return bool(self.win.winfo_exists())
        except tk.TclError:
            return False

    def _tick(self) -> None:
        """Entries expire while the window is open: read the log again now and then, so they leave the list too."""
        if not self.alive():
            return
        self.reload(force=True)
        self.win.after(TICK_MS, self._tick)

    def reload(self, force: bool = False) -> None:
        path = self.log().path
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0.0
        if not force and mtime == self.mtime and self.entries:
            return
        self.mtime = mtime
        keep = self._selected()
        fresh = self.log().entries(limit=1000)
        if force and self.entries and [e.get("id") for e in fresh] == [e.get("id") for e in self.entries]:
            return  # nothing expired or arrived: leave the list and the selection as they are
        self.entries = fresh
        self.list.delete(0, "end")
        for e in self.entries:
            self.list.insert("end", self.row(e, self.entries))
        if not self.entries:
            self.list.insert("end", self.empty_text())
        index = next((i for i, e in enumerate(self.entries) if keep and e.get("id") == keep.get("id")), 0)
        if self.entries:
            self.list.selection_set(index)
            self.list.activate(index)
            self.list.see(index)
        self._show()

    def _selected(self) -> dict | None:
        sel = self.list.curselection() if self.entries else ()
        return self.entries[sel[0]] if sel and sel[0] < len(self.entries) else None

    def _show(self) -> None:
        e = self._selected()
        for t in (self.before, self.after):
            t.delete("1.0", "end")
        state = "normal" if e else "disabled"
        for b in (self.copy_before, self.copy_after):
            b.configure(state=state)
        self.update_buttons(e)
        if not e:
            self.detail.configure(text="")
            return
        before, after = self.labels(e)
        self.before_label.configure(text=before)
        self.after_label.configure(text=after)
        left, right = diff_spans(e.get("before") or "", e.get("after") or "")
        for widget, spans in ((self.before, left), (self.after, right)):
            for text, changed in spans:
                widget.insert("end", text.replace("\r\n", "\n"), ("chg",) if changed else ())
        bits = [str(e.get("time") or "").replace("T", " ")[:19], e.get("window") or e.get("app") or ""]
        if e.get("model"):
            bits.append(f"{e['model']}" + (f" ({e['served']})" if e.get("served") and e["served"] != e["model"] else "")
                        + (f", {e['seconds']} s" if e.get("seconds") else ""))
        elif e.get("kind") == "dictation":
            bits.append(f"{e.get('seconds') or 0} s of speech" + (f", {e['style']} cleanup" if e.get("mode") == "polish"
                                                                   and e.get("style") else ", typed as you spoke"
                                                                   if e.get("mode") == "live" else ""))
        if e.get("note"):
            bits.append(str(e["note"]))
        self.detail.configure(text="  ·  ".join(b for b in bits if b))

    # ---------------------------------------------------------------- actions

    def _copy(self, field: str) -> None:
        e = self._selected()
        if e and e.get(field):
            self.app.copy_text(str(e[field]).strip())
            self.detail.configure(text=self.copied_text(field))

    def _revert(self) -> None:
        e = self._selected()
        if e:
            self.app.refine_revert(e.get("id") or "")

    def _open_folder(self) -> None:
        path: Path = self.log().path
        try:
            if os.name == "nt":
                if path.exists():
                    subprocess.Popen(["explorer", f"/select,{path}"])
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    os.startfile(path.parent)  # type: ignore[attr-defined]
        except OSError as e:
            self.detail.configure(text=f"Could not open the folder: {e}")

    def close(self) -> None:
        type(self)._open = None
        try:
            self.win.destroy()
        except tk.TclError:
            pass


def voice_row_text(e: dict) -> str:
    when = str(e.get("time") or "")[5:16].replace("T", " ")
    app = (e.get("app") or "").removesuffix(".exe")
    status = VOICE_STATUS.get(e.get("status"), e.get("status") or "")
    words = " ".join(str(e.get("after") or e.get("before") or "").split())
    return f"{when}   {app[:12]:<12}  {status:<14}  {words[:90]}"


class VoiceHistoryWindow(HistoryWindow):
    """What you dictated in the last dictation.keep_minutes: the transcript as heard next to the text typed (the
    cleanup's changes marked), with Copy and Type again."""
    _open: "VoiceHistoryWindow | None" = None
    TITLE = "Voice typing history"

    def log(self):
        return self.app.voice_log

    def intro(self) -> str:
        return (f"What you dictated is kept for {self.app.voice_keep_text()} in {self.log().path}, then deleted. "
                "Type again puts the typed text into the app you were in before this window.")

    def empty_text(self) -> str:
        return f"  Nothing dictated in the last {self.app.voice_keep_text()}. Click the mic or press its hotkey."

    def row(self, e: dict, entries: list[dict]) -> str:
        return voice_row_text(e)

    def make_buttons(self, frame) -> None:
        self.copy_before = self._button(frame, "Copy transcript", lambda: self._copy("before"))
        self.copy_after = self._button(frame, "Copy typed text", lambda: self._copy("after"))
        self.again_button = self._button(frame, "Type again in the app", self._again)

    def update_buttons(self, e: dict | None) -> None:
        self.again_button.configure(state="normal" if e and e.get("after") else "disabled")

    def labels(self, e: dict) -> tuple[str, str]:
        return "Heard (Whisper)", "Typed" if e.get("status") == "inserted" else "Text (not typed)"

    def copied_text(self, field: str) -> str:
        return ("Transcript" if field == "before" else "Typed text") + " copied to the clipboard."

    def _again(self) -> None:
        e = self._selected()
        if e and e.get("after"):
            self.app.paste_text(str(e["after"]))
            self.detail.configure(text="Typing it into the app you came from.")
