"""The floating mic button and its bubble (Tk). Both windows never take focus, so the caret stays where you type.

Button states: idle (grey mic), listening (red, with a level bar), working (blue, with a spinner), done (green check),
error (red "!"). The bubble above the button shows what is happening, the words as Whisper hears them, and the text
that was typed. Left click: start or stop. Drag: move (the position is remembered). Right click: options.
All Tk calls happen on the main thread; other threads hand work over with post().
"""
from __future__ import annotations

import os
import queue
import tkinter as tk
import tkinter.font as tkfont
from typing import Callable

from .cleanup import STYLE_NAMES
from .models import LANGUAGES

IS_WINDOWS = os.name == "nt"
FONT = "Segoe UI" if IS_WINDOWS else "TkDefaultFont"
# Dark surfaces read on any wallpaper or app. Text colours pass 4.5:1 on BG (WCAG AA); white passes on every state fill.
BG, BORDER, FG, MUTED = "#1f1f1f", "#3d3d3d", "#f3f3f3", "#b4b4b4"
STATE_FILL = {"idle": "#2d2d2d", "listening": "#c42b1c", "working": "#0f6cbd", "done": "#107c10", "error": "#c42b1c"}
STATE_INK = {"idle": FG, "listening": "#ff9a8f", "working": "#8cc8ff", "done": "#7fd67f", "error": "#ff9a8f"}
GLYPHS = {"mic": "", "check": "", "error": ""}
FALLBACK_GLYPHS = {"mic": "●", "check": "✓", "error": "!"}


class Overlay:
    def __init__(self, app, show_button: bool, position: tuple[int, int] | None) -> None:
        self.app = app
        self.q: queue.Queue = queue.Queue()
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("Voice typing")
        self.scale = max(1.0, self.root.winfo_fpixels("1i") / 96.0)
        self.size = int(44 * self.scale)
        families = set(tkfont.families(self.root))
        self.icon_font = next((f for f in ("Segoe Fluent Icons", "Segoe MDL2 Assets") if f in families), None)
        self.state = "idle"
        self.level = 0.0
        self.spin = 0
        self.hide_job: str | None = None
        self.hover_job: str | None = None
        self.drag: tuple[int, int, int, int] | None = None
        self.dragged = False
        self.show_button = show_button
        self.bubble_owner = ""   # "hover" while the hover hint is up, else the state that opened it

        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=BG)
        self.canvas = tk.Canvas(self.root, width=self.size, height=self.size, bg=STATE_FILL["idle"],
                                highlightthickness=0, bd=0, cursor="hand2")
        self.canvas.pack()
        self.glyph = self.canvas.create_text(self.size / 2, self.size / 2 - self.scale, text=self._g("mic"),
                                             fill=FG, font=self._icon(16))
        bar_h = max(2, int(3 * self.scale))
        self.bar = self.canvas.create_rectangle(0, self.size - bar_h, 0, self.size, fill="#ffffff", width=0)
        pad = 5 * self.scale
        self.arc = self.canvas.create_arc(pad, pad, self.size - pad, self.size - pad, start=0, extent=0,
                                          style="arc", outline="#ffffff", width=max(2, int(2 * self.scale)))
        for seq, fn in (("<ButtonPress-1>", self._press), ("<B1-Motion>", self._motion),
                        ("<ButtonRelease-1>", self._release), ("<Button-3>", self._menu),
                        ("<Enter>", self._enter), ("<Leave>", self._leave)):
            self.canvas.bind(seq, fn)

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
        x, y = position or (sw - self.size - int(28 * self.scale), sh - self.size - int(96 * self.scale))
        x, y = min(max(0, x), sw - self.size), min(max(0, y), sh - self.size)
        self.root.geometry(f"{self.size}x{self.size}+{x}+{y}")
        self.root.update_idletasks()
        self._hwnds: set[int] = set()
        self._style_windows()
        if show_button:
            self.root.deiconify()
        self.root.after(30, self._drain)
        self.root.after(50, self._animate)

    # ---------------------------------------------------------------- plumbing

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
        """Top-level HWNDs of the button and bubble, which text must never go into. Read once on the Tk thread, so
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

    # ---------------------------------------------------------------- state (call through post())

    def set_state(self, state: str, title: str = "", body: str = "", hint: str = "", hide_after: float = 0.0) -> None:
        self.state = state
        self.canvas.configure(bg=STATE_FILL.get(state, STATE_FILL["idle"]))
        glyph = {"done": "check", "error": "error"}.get(state, "mic")
        self.canvas.itemconfigure(self.glyph, text=self._g(glyph))
        if state != "listening":
            self.level = 0.0
            self.canvas.coords(self.bar, 0, self.size, 0, self.size)
        if state != "working":
            self.canvas.itemconfigure(self.arc, extent=0)
        if title or body:
            self.show_bubble(title, body, hint, ink=STATE_INK.get(state, FG), owner=state)
        if hide_after:
            self._schedule_hide(hide_after)
        elif self.hide_job:
            self.root.after_cancel(self.hide_job)
            self.hide_job = None

    def set_level(self, value: float) -> None:
        if self.state != "listening":
            return
        self.level = self.level * 0.4 + value * 0.6
        bar_h = max(2, int(3 * self.scale))
        self.canvas.coords(self.bar, 0, self.size - bar_h, self.size * min(1.0, self.level), self.size)

    def set_text(self, body: str) -> None:
        """Replace only the transcript line of the open bubble."""
        if self.bubble.winfo_viewable():
            self.body.configure(text=_tail(body, 260), fg=FG)
            self._place_bubble()

    def show_bubble(self, title: str, body: str = "", hint: str = "", ink: str = FG, owner: str = "") -> None:
        self.bubble_owner = owner
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

    def _schedule_hide(self, seconds: float) -> None:
        if self.hide_job:
            self.root.after_cancel(self.hide_job)
        self.hide_job = self.root.after(int(seconds * 1000), self._auto_hide)

    def _auto_hide(self) -> None:
        self.hide_job = None
        if self.state in ("done", "error", "idle"):
            self.hide_bubble()
            if self.state != "idle":
                self.set_state("idle")

    def _place_bubble(self) -> None:
        self.bubble.update_idletasks()
        bw, bh = self.bubble.winfo_reqwidth(), self.bubble.winfo_reqheight()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        if self.show_button:
            x0, y0 = self.root.winfo_x(), self.root.winfo_y()
        else:  # no button: the bubble sits where the button would be, bottom right
            x0, y0 = sw - self.size - int(28 * self.scale), sh - self.size - int(96 * self.scale)
        gap = int(8 * self.scale)
        x = x0 + self.size - bw if x0 + self.size / 2 > sw / 2 else x0
        y = y0 - bh - gap if y0 - bh - gap > 0 else y0 + self.size + gap
        x = min(max(0, x), sw - bw)
        self.bubble.geometry(f"+{x}+{y}")

    def set_button_visible(self, visible: bool) -> None:
        self.show_button = visible
        if visible:
            self.root.deiconify()
            self.root.lift()
        else:
            self.root.withdraw()

    def _animate(self) -> None:
        if self.state == "working":
            self.spin = (self.spin + 24) % 360
            self.canvas.itemconfigure(self.arc, start=self.spin, extent=100)
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

    def _release(self, _e) -> None:
        if self.dragged:
            self.app.remember_position(self.root.winfo_x(), self.root.winfo_y())
        else:
            self._cancel_hover()
            self.app.toggle("button")
        self.drag = None
        self.dragged = False

    def _enter(self, _e) -> None:
        if self.state == "idle" and not self.bubble.winfo_viewable():
            self.hover_job = self.root.after(700, self._hover_hint)

    def _leave(self, _e) -> None:
        self._cancel_hover()
        if self.bubble_owner == "hover":
            self.hide_bubble()

    def _cancel_hover(self) -> None:
        if self.hover_job:
            self.root.after_cancel(self.hover_job)
            self.hover_job = None

    def _hover_hint(self) -> None:
        self.hover_job = None
        if self.state == "idle":
            self.show_bubble("Voice typing", self.app.summary(),
                             f"Click or press {self.app.hotkey_text()} to talk (hold it to talk while held). "
                             "Right-click for options.", owner="hover")

    # ---------------------------------------------------------------- menu

    def _menu(self, e) -> None:
        self._cancel_hover()
        if self.bubble_owner == "hover":
            self.hide_bubble()
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
        lang = tk.StringVar(self.root, cfg.language)
        langs = tk.Menu(m, tearoff=0)
        for code, text in LANGUAGES:
            langs.add_radiobutton(label=text, variable=lang, value=code, command=lambda c=code: app.set_option("language", c))
        current = dict(LANGUAGES).get(cfg.language, cfg.language)
        m.add_cascade(label=f"Language: {current}", menu=langs)
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
        m.add_command(label="Hide button (the hotkey still works)", command=lambda: app.set_option("button", False))
        m.add_command(label="Quit voice typing", command=app.quit)
        # Keep references alive while the menu is open (Tk variables die with their Python objects).
        m._vars = (mode, style, lang, insert)  # type: ignore[attr-defined]
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()


def _tail(text: str, limit: int) -> str:
    text = " ".join((text or "").split()) if "\n" not in (text or "") else (text or "").strip()
    return text if len(text) <= limit else "…" + text[-(limit - 1):]
