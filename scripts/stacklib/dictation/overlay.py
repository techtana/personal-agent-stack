"""The floating buttons and their bubble (Tk): the mic for voice typing and, beside it, the refine button for selected
text. Neither window ever takes the focus, so the caret and the selection stay in the app you work in.

Button states: idle (grey), listening (red, mic only, with a level bar), working (blue, with a spinner), done (green
check), error (red "!"). The bubble above the buttons shows what is happening: the words as Whisper hears them, the
text that was typed, or the refined text. Left click: start (dictate, or refine the selection). Drag either button:
move both (the position is remembered). Right click: options (the menu closes half a second after the pointer leaves
it and the buttons). All Tk calls happen on the main thread; other threads hand work over with post().
"""
from __future__ import annotations

import os
import queue
import tkinter as tk
import tkinter.font as tkfont
from typing import Callable

from .cleanup import STYLE_NAMES
from .models import language_name, languages_for, search

IS_WINDOWS = os.name == "nt"
FONT = "Segoe UI" if IS_WINDOWS else "TkDefaultFont"
# Dark surfaces read on any wallpaper or app. Text colours pass 4.5:1 on BG (WCAG AA); white passes on every state fill.
BG, BORDER, FG, MUTED = "#1f1f1f", "#3d3d3d", "#f3f3f3", "#b4b4b4"
STATE_FILL = {"idle": "#2d2d2d", "listening": "#c42b1c", "working": "#0f6cbd", "done": "#107c10", "error": "#c42b1c"}
STATE_INK = {"idle": FG, "listening": "#ff9a8f", "working": "#8cc8ff", "done": "#7fd67f", "error": "#ff9a8f"}
GLYPHS = {"mic": "", "pen": "", "check": "", "error": ""}
FALLBACK_GLYPHS = {"mic": "●", "pen": "✎", "check": "✓", "error": "!"}
BUTTONS = ("refine", "mic")   # left to right
MENU_POLL_MS = 100    # how often the open right-click menu checks the pointer
MENU_LEAVE_MS = 500   # the menu closes after the pointer has been off it (and off the buttons) this long


class Overlay:
    def __init__(self, app, show_button: bool, position: tuple[int, int] | None, show_refine: bool = False,
                 saved_width: int = 0) -> None:
        self.app = app
        self.q: queue.Queue = queue.Queue()
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("Voice typing")
        self.scale = max(1.0, self.root.winfo_fpixels("1i") / 96.0)
        self.size = int(44 * self.scale)
        self.gap = max(2, int(4 * self.scale))
        families = set(tkfont.families(self.root))
        self.icon_font = next((f for f in ("Segoe Fluent Icons", "Segoe MDL2 Assets") if f in families), None)
        self.states = {"mic": "idle", "refine": "idle"}
        self.visible = {"mic": bool(show_button), "refine": bool(show_refine)}
        self.hide_jobs: dict[str, str | None] = {"mic": None, "refine": None}
        self.level = 0.0
        self.spin = 0
        self.hover_job: str | None = None
        self.drag: tuple[int, int, int, int] | None = None
        self.dragged = False
        self.bubble_owner = ""   # "hover" while the hover hint is up, else the state that opened it
        self.bubble_from = ""    # which button the bubble speaks for: mic | refine
        self.menu_open: tk.Menu | None = None

        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=BG)
        self.bar = tk.Frame(self.root, bg=BG)
        self.bar.pack()
        self.canvases: dict[str, tk.Canvas] = {}
        self.glyphs: dict[str, int] = {}
        self.arcs: dict[str, int] = {}
        pad = 5 * self.scale
        for which in BUTTONS:
            c = tk.Canvas(self.bar, width=self.size, height=self.size, bg=STATE_FILL["idle"], highlightthickness=0,
                          bd=0, cursor="hand2")
            self.canvases[which] = c
            idle = "pen" if which == "refine" else "mic"
            self.glyphs[which] = c.create_text(self.size / 2, self.size / 2 - self.scale, text=self._g(idle), fill=FG,
                                               font=self._icon(15 if which == "refine" else 16))
            self.arcs[which] = c.create_arc(pad, pad, self.size - pad, self.size - pad, start=0, extent=0,
                                            style="arc", outline="#ffffff", width=max(2, int(2 * self.scale)))
            for seq, fn in (("<ButtonPress-1>", self._press), ("<B1-Motion>", self._motion),
                            ("<ButtonRelease-1>", lambda e, w=which: self._release(e, w)),
                            ("<Button-3>", self._menu if which == "mic" else self._refine_menu),
                            ("<Enter>", lambda e, w=which: self._enter(w)), ("<Leave>", lambda e, w=which: self._leave(w))):
                c.bind(seq, fn)
        self.canvas = self.canvases["mic"]
        bar_h = max(2, int(3 * self.scale))
        self.level_bar = self.canvas.create_rectangle(0, self.size - bar_h, 0, self.size, fill="#ffffff", width=0)

        self.bubble = tk.Toplevel(self.root)
        self.bubble.withdraw()
        self.bubble.overrideredirect(True)
        self.bubble.attributes("-topmost", True)
        self.bubble.configure(bg=BORDER)
        inner = tk.Frame(self.bubble, bg=BG, padx=int(12 * self.scale), pady=int(9 * self.scale))
        inner.pack(padx=1, pady=1)
        self.wrap = int(340 * self.scale)
        self.title = tk.Label(inner, text="", bg=BG, fg=FG, font=(FONT, 9, "bold"), anchor="w", justify="left")
        self.title.pack(anchor="w", fill="x")
        self.body = tk.Label(inner, text="", bg=BG, fg=FG, font=(FONT, 10), anchor="w", justify="left",
                             wraplength=self.wrap)
        self.body.pack(anchor="w", fill="x", pady=(int(3 * self.scale), 0))
        self.hint = tk.Label(inner, text="", bg=BG, fg=MUTED, font=(FONT, 8), anchor="w", justify="left",
                             wraplength=self.wrap)
        self.hint.pack(anchor="w", fill="x", pady=(int(4 * self.scale), 0))

        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        width = self._bar_width()
        if position:
            x, y = position
            old = saved_width or self.size   # positions saved before the refine button existed were for the mic alone
            if x + old / 2 > sw / 2:
                x += old - width             # on the right half: keep the right edge, so the mic stays put
        else:
            x, y = sw - width - int(28 * self.scale), sh - self.size - int(96 * self.scale)
        x, y = min(max(0, x), sw - width), min(max(0, y), sh - self.size)
        self.root.geometry(f"{width}x{self.size}+{x}+{y}")
        self._layout(keep_right=False, show=False)
        self.root.update_idletasks()
        self._hwnds: set[int] = set()
        self._style_windows()  # before the first show, so showing it cannot take the focus
        if any(self.visible.values()):
            self.root.deiconify()
        self.root.after(30, self._drain)
        self.root.after(50, self._animate)

    # ---------------------------------------------------------------- plumbing

    @property
    def state(self) -> str:
        """The mic button's state (voice typing)."""
        return self.states["mic"]

    @property
    def show_button(self) -> bool:
        return self.visible["mic"]

    def _g(self, name: str) -> str:
        return GLYPHS[name] if self.icon_font else FALLBACK_GLYPHS[name]

    def _icon(self, points: int):
        return (self.icon_font, points) if self.icon_font else (FONT, points, "bold")

    def _style_windows(self) -> None:
        if not IS_WINDOWS:
            return
        from . import winsys

        for win in (self.root, self.bubble):
            try:
                hwnd = int(win.wm_frame(), 16)
                winsys.make_overlay(hwnd)
                winsys.round_corners(hwnd)
                self._hwnds.add(hwnd)
            except (ValueError, tk.TclError, OSError) as e:
                print(f"[dictation] window style not applied: {e}", flush=True)

    def windows(self) -> set[int]:
        """Top-level HWNDs of the buttons and bubble, which text must never go into. Read once on the Tk thread, so
        other threads can ask without calling into Tk (which is not thread-safe)."""
        return set(self._hwnds)

    def post(self, fn: Callable[[], None]) -> None:
        self.q.put(fn)

    def _drain(self) -> None:
        try:
            while True:
                fn = self.q.get_nowait()
                try:
                    fn()
                except Exception as e:  # noqa: BLE001 - one bad update must not stop the UI loop
                    print(f"[dictation] ui update failed: {e}", flush=True)
        except queue.Empty:
            pass
        self.root.after(30, self._drain)

    def run(self) -> None:
        self.root.mainloop()

    def quit(self) -> None:
        self.root.quit()

    # ---------------------------------------------------------------- layout

    def _shown(self) -> list[str]:
        return [w for w in BUTTONS if self.visible[w]]

    def _bar_width(self) -> int:
        n = len(self._shown())
        return n * self.size + max(0, n - 1) * self.gap if n else self.size

    def _layout(self, keep_right: bool = True, show: bool = True) -> None:
        """Show the visible buttons side by side; with keep_right the bar keeps its right edge on the right half of
        the screen (where it starts), so the mic does not jump when the refine button comes or goes."""
        old_w, x, y = self.root.winfo_width(), self.root.winfo_x(), self.root.winfo_y()
        for c in self.canvases.values():
            c.pack_forget()
        for i, w in enumerate(self._shown()):
            self.canvases[w].pack(side="left", padx=(self.gap if i else 0, 0))
        width = self._bar_width()
        if keep_right:
            sw = self.root.winfo_screenwidth()
            if old_w > 1 and x + old_w / 2 > sw / 2:
                x += old_w - width
            x = min(max(0, x), sw - width)
            self.root.geometry(f"{width}x{self.size}+{x}+{y}")
        if not show:
            return
        if self._shown():
            self.root.deiconify()
            self.root.lift()
        else:
            self.root.withdraw()

    def bar_box(self) -> tuple[int, int, int, int]:
        """(x, y, width, height) of the buttons, or of where they would be when both are hidden."""
        if self._shown():
            return self.root.winfo_x(), self.root.winfo_y(), self._bar_width(), self.size
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        return sw - self.size - int(28 * self.scale), sh - self.size - int(96 * self.scale), self.size, self.size

    def set_button_visible(self, visible: bool) -> None:
        self.visible["mic"] = bool(visible)
        self._layout()

    def set_refine_visible(self, visible: bool) -> None:
        self.visible["refine"] = bool(visible)
        self._layout()

    # ---------------------------------------------------------------- state (call through post())

    def set_state(self, state: str, title: str = "", body: str = "", hint: str = "", hide_after: float = 0.0,
                  which: str = "mic") -> None:
        self.states[which] = state
        c = self.canvases[which]
        c.configure(bg=STATE_FILL.get(state, STATE_FILL["idle"]))
        idle = "pen" if which == "refine" else "mic"
        c.itemconfigure(self.glyphs[which], text=self._g({"done": "check", "error": "error"}.get(state, idle)))
        if which == "mic" and state != "listening":
            self.level = 0.0
            self.canvas.coords(self.level_bar, 0, self.size, 0, self.size)
        if state != "working":
            c.itemconfigure(self.arcs[which], extent=0)
        if title or body:
            self.show_bubble(title, body, hint, ink=STATE_INK.get(state, FG), owner=state, source=which)
        if hide_after:
            self._schedule_hide(hide_after, which)
        elif self.hide_jobs[which]:
            self.root.after_cancel(self.hide_jobs[which])
            self.hide_jobs[which] = None

    def set_level(self, value: float) -> None:
        if self.states["mic"] != "listening":
            return
        self.level = self.level * 0.4 + value * 0.6
        bar_h = max(2, int(3 * self.scale))
        self.canvas.coords(self.level_bar, 0, self.size - bar_h, self.size * min(1.0, self.level), self.size)

    def set_text(self, body: str) -> None:
        """Replace only the transcript line of the open bubble."""
        if self.bubble.winfo_viewable():
            self.body.configure(text=_tail(body, 260), fg=FG)
            self._place_bubble()

    def show_bubble(self, title: str, body: str = "", hint: str = "", ink: str = FG, owner: str = "",
                    source: str = "mic") -> None:
        self.bubble_owner = owner
        self.bubble_from = source
        self.title.configure(text=title, fg=ink)
        self.body.configure(text=_tail(body, 260))
        self.body.pack_forget() if not body else self.body.pack(anchor="w", fill="x", pady=(int(3 * self.scale), 0))
        self.hint.configure(text=hint)
        self.hint.pack_forget() if not hint else self.hint.pack(anchor="w", fill="x", pady=(int(4 * self.scale), 0))
        self._place_bubble()
        self.bubble.deiconify()
        self.bubble.lift()
        if IS_WINDOWS and not getattr(self, "_bubble_checked", False):
            self._bubble_checked = True  # Tk may create the wrapper window on first map: style it again
            from . import winsys

            try:
                hwnd = int(self.bubble.wm_frame(), 16)
                winsys.make_overlay(hwnd)
                self._hwnds.add(hwnd)
            except (ValueError, tk.TclError, OSError):
                pass

    def hide_bubble(self) -> None:
        self.bubble.withdraw()
        self.bubble_owner = ""
        self.bubble_from = ""

    def _schedule_hide(self, seconds: float, which: str = "mic") -> None:
        if self.hide_jobs[which]:
            self.root.after_cancel(self.hide_jobs[which])
        self.hide_jobs[which] = self.root.after(int(seconds * 1000), lambda: self._auto_hide(which))

    def _auto_hide(self, which: str = "mic") -> None:
        self.hide_jobs[which] = None
        if self.states[which] in ("done", "error", "idle"):
            if self.bubble_from in (which, ""):
                self.hide_bubble()
            if self.states[which] != "idle":
                self.set_state("idle", which=which)

    def _place_bubble(self) -> None:
        self.bubble.update_idletasks()
        bw, bh = self.bubble.winfo_reqwidth(), self.bubble.winfo_reqheight()
        sw = self.root.winfo_screenwidth()
        x0, y0, w0, h0 = self.bar_box()
        gap = int(8 * self.scale)
        x = x0 + w0 - bw if x0 + w0 / 2 > sw / 2 else x0
        y = y0 - bh - gap if y0 - bh - gap > 0 else y0 + h0 + gap
        x = min(max(0, x), sw - bw)
        self.bubble.geometry(f"+{x}+{y}")

    def _animate(self) -> None:
        if "working" in self.states.values():
            self.spin = (self.spin + 24) % 360
            for which, state in self.states.items():
                if state == "working":
                    self.canvases[which].itemconfigure(self.arcs[which], start=self.spin, extent=100)
        self.root.after(50, self._animate)

    # ---------------------------------------------------------------- mouse

    def _press(self, e) -> None:
        self.drag = (e.x_root, e.y_root, self.root.winfo_x(), self.root.winfo_y())
        self.dragged = False

    def _motion(self, e) -> None:
        if not self.drag:
            return
        dx, dy = e.x_root - self.drag[0], e.y_root - self.drag[1]
        if not self.dragged and abs(dx) + abs(dy) < 6 * self.scale:
            return
        self.dragged = True
        self.root.geometry(f"+{self.drag[2] + dx}+{self.drag[3] + dy}")
        if self.bubble.winfo_viewable():
            self._place_bubble()

    def _release(self, _e, which: str) -> None:
        if self.dragged:
            self.app.remember_position(self.root.winfo_x(), self.root.winfo_y(), self._bar_width())
        else:
            self._cancel_hover()
            if which == "mic":
                self.app.toggle("button")
            else:
                self.app.refine_click()
        self.drag = None
        self.dragged = False

    def _enter(self, which: str) -> None:
        if self.states[which] == "idle" and not self.bubble.winfo_viewable():
            self.hover_job = self.root.after(700, lambda: self._hover_hint(which))

    def _leave(self, _which: str) -> None:
        self._cancel_hover()
        if self.bubble_owner == "hover":
            self.hide_bubble()

    def _cancel_hover(self) -> None:
        if self.hover_job:
            self.root.after_cancel(self.hover_job)
            self.hover_job = None

    def _hover_hint(self, which: str) -> None:
        self.hover_job = None
        if self.states[which] != "idle":
            return
        if which == "mic":
            self.show_bubble("Voice typing", self.app.summary(),
                             f"Click or press {self.app.hotkey_text()} to talk (hold it to talk while held). "
                             "Right-click for options.", owner="hover", source="mic")
        else:
            key = self.app.refine_hotkey_text()
            self.show_bubble("Refine selected text", self.app.refine_summary(),
                             "Select text in any app, then click here" + (f" or press {key}" if key else "") +
                             ". Right-click for other styles, revert and history.", owner="hover", source="refine")

    # ---------------------------------------------------------------- menus

    def _close_hover(self) -> None:
        self._cancel_hover()
        if self.bubble_owner == "hover":
            self.hide_bubble()

    def _popup(self, m: tk.Menu, e) -> None:
        """Show a right-click menu. It closes once the pointer has been off it and off the buttons for MENU_LEAVE_MS."""
        self.menu_open = m
        self.root.after(MENU_POLL_MS, self._watch_menu, m, 0)
        try:
            m.tk_popup(e.x_root, e.y_root)  # on Windows this blocks in the native menu loop; Tk timers still run
        finally:
            m.grab_release()
            if IS_WINDOWS:
                self.menu_open = None

    def _menu(self, e) -> None:
        self._close_hover()
        app, cfg = self.app, self.app.cfg
        m = tk.Menu(self.root, tearoff=0)
        busy = app.state != "idle"
        m.add_command(label="Stop" if app.state == "listening" else "Dictate",
                      accelerator=app.hotkey_text(), command=lambda: app.toggle("button"),
                      state="disabled" if app.state == "finishing" else "normal")
        m.add_separator()
        mode = tk.StringVar(self.root, cfg.mode)
        m.add_radiobutton(label="Type when I finish, cleaned up", variable=mode, value="polish",
                          command=lambda: app.set_option("mode", "polish"))
        m.add_radiobutton(label="Type as I speak", variable=mode, value="live",
                          command=lambda: app.set_option("mode", "live"))
        style = tk.StringVar(self.root, cfg.style)
        sub = tk.Menu(m, tearoff=0)
        for key, text in (("verbatim", "Verbatim (as heard)"), ("clean", "Clean (fillers, false starts)"),
                          ("concise", "Concise (also shorter)")):
            sub.add_radiobutton(label=text, variable=style, value=key, command=lambda k=key: app.set_option("style", k))
        m.add_cascade(label=f"Cleanup: {STYLE_NAMES.get(cfg.style, cfg.style)}", menu=sub)
        # 100 languages are too many for a submenu: open the search picker instead.
        m.add_command(label=f"Language: {language_name(cfg.language)}...", command=self.pick_language)
        insert = tk.StringVar(self.root, cfg.insert)
        ins = tk.Menu(m, tearoff=0)
        ins.add_radiobutton(label="Paste (fast; clipboard restored)", variable=insert, value="paste",
                            command=lambda: app.set_option("insert", "paste"))
        ins.add_radiobutton(label="Type keystrokes", variable=insert, value="type",
                            command=lambda: app.set_option("insert", "type"))
        m.add_cascade(label="Insert by: " + ("pasting" if cfg.insert == "paste" else "typing"), menu=ins)
        m.add_separator()
        last = "normal" if app.history else "disabled"
        m.add_command(label="Paste last text again", state=last if not busy else "disabled", command=app.paste_last)
        m.add_command(label="Copy last text", state=last, command=lambda: app.copy_last(raw=False))
        m.add_command(label="Copy last transcript as heard", state=last, command=lambda: app.copy_last(raw=True))
        m.add_separator()
        if not self.visible["refine"]:
            m.add_command(label="Show the refine button", command=lambda: app.set_refine_option("button", True))
        m.add_command(label="Hide button (the hotkey still works)", command=lambda: app.set_option("button", False))
        m.add_command(label="Quit voice typing", command=app.quit)
        # Keep references alive while the menu is open (Tk variables die with their Python objects).
        m._vars = (mode, style, insert)  # type: ignore[attr-defined]
        self._popup(m, e)

    def _refine_menu(self, e) -> None:
        self._close_hover()
        app = self.app
        styles, default = app.refine_choices()
        ready = "disabled" if app.refine_busy() or app.state != "idle" else "normal"
        m = tk.Menu(self.root, tearoff=0)
        for s in styles:
            m.add_command(label=s.name, accelerator=app.refine_hotkey_text() if s.id == default else "", state=ready,
                          command=lambda sid=s.id: app.refine_with(sid))
        m.add_separator()
        chosen = tk.StringVar(self.root, default)
        sub = tk.Menu(m, tearoff=0)
        for s in styles:
            sub.add_radiobutton(label=s.name, variable=chosen, value=s.id,
                                command=lambda sid=s.id: app.set_refine_option("default", sid))
        name = next((s.name for s in styles if s.id == default), default)
        m.add_cascade(label=f"Click and hotkey use: {name}", menu=sub)
        m.add_command(label="Add or edit styles...", command=app.edit_refine_styles)
        m.add_separator()
        m.add_command(label="Revert selected text to the original", state=ready, command=lambda: app.refine_revert(""))
        m.add_command(label="Refine history...", command=self.open_history)
        m.add_separator()
        m.add_command(label="Hide this button (the hotkey still works)",
                      command=lambda: app.set_refine_option("button", False))
        m._vars = (chosen,)  # type: ignore[attr-defined]
        self._popup(m, e)

    def open_history(self) -> None:
        from .history import HistoryWindow

        self.hide_bubble()
        HistoryWindow(self.root, self.app)

    def _menu_rects(self, m: tk.Menu) -> list[tuple[int, int, int, int]]:
        """Where the pointer may be while the menu should stay open: the buttons and every open (sub)menu."""
        rects = []
        if self._shown():
            x, y = self.root.winfo_rootx(), self.root.winfo_rooty()
            rects.append((x, y, x + self._bar_width(), y + self.size))
        if IS_WINDOWS:
            from . import winsys

            return rects + winsys.popup_menu_rects()
        for w in [m, *(m.nametowidget(c) for c in m.winfo_children())]:
            if w.winfo_ismapped():
                x, y = w.winfo_rootx(), w.winfo_rooty()
                rects.append((x, y, x + w.winfo_width(), y + w.winfo_height()))
        return rects

    def _watch_menu(self, m: tk.Menu, outside_ms: int) -> None:
        """Close the right-click menu once the pointer has been off it (and off the buttons) for MENU_LEAVE_MS."""
        if self.menu_open is not m:
            return
        try:
            if not IS_WINDOWS and not m.winfo_ismapped():
                self.menu_open = None
                return
            if IS_WINDOWS:
                from . import winsys

                point = winsys.cursor_pos()
            else:
                point = self.root.winfo_pointerxy()
            rects = self._menu_rects(m)
        except (tk.TclError, OSError):
            return
        outside_ms = 0 if pointer_inside(point, rects) else outside_ms + MENU_POLL_MS
        if outside_ms >= MENU_LEAVE_MS:
            self.menu_open = None
            if IS_WINDOWS:
                from . import winsys

                winsys.end_menu()
            else:
                m.unpost()
            return
        self.root.after(MENU_POLL_MS, self._watch_menu, m, outside_ms)

    def pick_language(self) -> None:
        """The search picker above the buttons (or where they would be when hidden)."""
        from .picker import Picker

        self.hide_bubble()
        Picker(self.root, languages_for(self.app.cfg.model), self.app.cfg.language,
               lambda code: self.app.set_option("language", code), search, title="Dictation language",
               anchor=self.bar_box(), above=True)


def pointer_inside(point: tuple[int, int], rects: list[tuple[int, int, int, int]], margin: int = 4) -> bool:
    """True if the point is within any (left, top, right, bottom) rectangle, grown by a few pixels so the gap
    between a menu and its submenu, or the button's edge, does not count as leaving."""
    x, y = point
    return any(l - margin <= x < r + margin and t - margin <= y < b + margin for l, t, r, b in rects)


def _tail(text: str, limit: int) -> str:
    text = " ".join((text or "").split()) if "\n" not in (text or "") else (text or "").strip()
    return text if len(text) <= limit else "…" + text[-(limit - 1):]
