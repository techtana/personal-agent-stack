"""A small searchable list for picking one of many values (Whisper's 100 languages, the read aloud voices), shared by
the buttons' menus and the tray's Settings tab. Type to filter by substring (names, other names and codes); Up and
Down move; Enter or a click chooses; Esc, or clicking elsewhere, closes. It takes the keyboard focus while open, unlike
the buttons.
"""
from __future__ import annotations

import os
import tkinter as tk
from typing import Callable

FONT = "Segoe UI" if os.name == "nt" else "TkDefaultFont"
# Text colours pass 4.5:1 on their backgrounds (WCAG AA), as in the button's bubble and the tray's themes.
DARK = {"bg": "#1f1f1f", "field": "#2b2b2b", "fg": "#f3f3f3", "muted": "#b4b4b4", "border": "#3d3d3d",
        "select_bg": "#0f6cbd", "select_fg": "#ffffff", "accent": "#4ca0f0"}


class Picker:
    """One open picker at a time per master; choosing calls on_choose(code) and closes."""

    _open: dict[int, "Picker"] = {}

    def __init__(self, master: tk.Misc, items: list[tuple[str, str]], current: str,
                 on_choose: Callable[[str], None], search: Callable[[str, list], list], *, title: str = "Language",
                 anchor: tuple[int, int, int, int] | None = None, above: bool = False, palette: dict | None = None,
                 rows: int = 12, placeholder: str = "Search by name or code",
                 empty: str = "No language matches. Esc closes.", show_code: bool = True) -> None:
        old = Picker._open.pop(id(master), None)
        if old:
            old.close()
        Picker._open[id(master)] = self
        self.master, self.items, self.current = master, items, current
        self.on_choose, self.search = on_choose, search
        self.empty, self.show_code = empty, show_code
        self.shown: list[tuple[str, str]] = []
        self.closed = False
        p = {**DARK, **(palette or {})}
        scale = max(1.0, master.winfo_fpixels("1i") / 96.0)

        self.win = tk.Toplevel(master)
        self.win.withdraw()
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=p["border"])
        inner = tk.Frame(self.win, bg=p["bg"], padx=int(10 * scale), pady=int(8 * scale))
        inner.pack(padx=1, pady=1)
        tk.Label(inner, text=title, bg=p["bg"], fg=p["fg"], font=(FONT, 9, "bold"), anchor="w").pack(fill="x")
        self.query = tk.StringVar()
        self.entry = tk.Entry(inner, textvariable=self.query, width=34, font=(FONT, 10), relief="flat",
                              bg=p["field"], fg=p["fg"], insertbackground=p["fg"], highlightthickness=2,
                              highlightbackground=p["border"], highlightcolor=p["accent"])
        self.entry.pack(fill="x", pady=(int(6 * scale), int(6 * scale)), ipady=int(3 * scale))
        self.placeholder = tk.Label(self.entry, text=placeholder, bg=p["field"], fg=p["muted"], font=(FONT, 10))
        self.placeholder.place(x=4, rely=0.5, anchor="w")
        self.placeholder.bind("<Button-1>", lambda _e: self.entry.focus_set())
        box = tk.Frame(inner, bg=p["bg"])
        box.pack(fill="both", expand=True)
        self.list = tk.Listbox(box, height=rows, activestyle="none", exportselection=False, font=(FONT, 10),
                               relief="flat", highlightthickness=0, bg=p["bg"], fg=p["fg"],
                               selectbackground=p["select_bg"], selectforeground=p["select_fg"])
        bar = tk.Scrollbar(box, orient="vertical", command=self.list.yview)
        self.list.configure(yscrollcommand=bar.set)
        self.list.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        self.status = tk.Label(inner, text="", bg=p["bg"], fg=p["muted"], font=(FONT, 8), anchor="w")
        self.status.pack(fill="x", pady=(int(4 * scale), 0))

        self.query.trace_add("write", lambda *_: self._refill())
        for seq, step in (("<Down>", 1), ("<Up>", -1), ("<Next>", rows), ("<Prior>", -rows)):
            self.entry.bind(seq, lambda _e, s=step: self._move(s))
        self.entry.bind("<Return>", lambda _e: self._choose_selected())
        self.list.bind("<Return>", lambda _e: self._choose_selected())
        self.list.bind("<ButtonRelease-1>", self._click)
        for w in (self.win, self.entry, self.list):
            w.bind("<Escape>", lambda _e: self.close())
        self.win.bind("<FocusOut>", lambda _e: self.win.after(150, self._close_if_unfocused))

        self._refill()
        self._place(anchor, above, scale)
        self.win.deiconify()
        self.win.lift()
        self.win.focus_force()
        self.entry.focus_set()

    # ---------------------------------------------------------------- list

    def _refill(self) -> None:
        text = self.query.get()
        self.placeholder.place_forget() if text else self.placeholder.place(x=4, rely=0.5, anchor="w")
        self.shown = self.search(text, self.items)
        self.list.delete(0, "end")
        for code, name in self.shown:
            self.list.insert("end", name if code == "auto" or not self.show_code else f"{name}  ({code})")
        if not self.shown:
            self.status.configure(text=self.empty)
            return
        n = len(self.shown)
        self.status.configure(text=f"{n} of {len(self.items)}" if text else "Type to search. Enter chooses, Esc closes.")
        pick = 0
        if not text:
            pick = next((i for i, (code, _) in enumerate(self.shown) if code == self.current), 0)
        self._select(pick)

    def _select(self, index: int) -> None:
        if not self.shown:
            return
        index = max(0, min(index, len(self.shown) - 1))
        self.list.selection_clear(0, "end")
        self.list.selection_set(index)
        self.list.activate(index)
        self.list.see(index)

    def _move(self, step: int) -> str:
        sel = self.list.curselection()
        self._select((sel[0] if sel else -1) + step)
        return "break"

    def _click(self, e) -> None:
        index = self.list.nearest(e.y)
        if 0 <= index < len(self.shown):
            self._choose(self.shown[index][0])

    def _choose_selected(self) -> str:
        sel = self.list.curselection()
        if sel and self.shown:
            self._choose(self.shown[sel[0]][0])
        return "break"

    def _choose(self, code: str) -> None:
        self.close()
        self.on_choose(code)

    # ---------------------------------------------------------------- window

    def _place(self, anchor, above: bool, scale: float) -> None:
        self.win.update_idletasks()
        w, h = self.win.winfo_reqwidth(), self.win.winfo_reqheight()
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        if anchor is None:
            x, y = (sw - w) // 2, (sh - h) // 2
        else:
            ax, ay, aw, ah = anchor
            gap = int(6 * scale)
            x = ax + aw - w if ax + aw / 2 > sw / 2 else ax
            y = ay - h - gap if above else ay + ah + gap
            if y < 0 or y + h > sh:
                y = ay + ah + gap if above else ay - h - gap
        self.win.geometry(f"+{max(0, min(x, sw - w))}+{max(0, min(y, sh - h))}")

    def _close_if_unfocused(self) -> None:
        if self.closed:
            return
        try:
            focused = self.win.focus_get()
        except (KeyError, tk.TclError):  # focus is in a window of another program
            focused = None
        if focused is None or not str(focused).startswith(str(self.win)):
            self.close()

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        Picker._open.pop(id(self.master), None)
        try:
            self.win.destroy()
        except tk.TclError:
            pass
