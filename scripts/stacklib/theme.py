"""The window look the tray and the installer share: the light and dark palette, the system theme, and the ttk styles
(cards, filled buttons with an outline, the accent primary button, the danger-outlined destructive one, focus rings).

Change colours here once; scripts/tray.py and scripts/installer.py both call apply().
"""
from __future__ import annotations

from . import IS_WINDOWS

FONT = "Segoe UI" if IS_WINDOWS else "TkDefaultFont"

# Window palette (light / dark): neutral surfaces, one blue accent for data, status colours only for state.
# Every colour used for text (ink2, muted, accent, good, warn, bad) is at least 4.5:1 on page and card, and accent_ink
# at least 4.5:1 on accent (WCAG AA); check changes with .claude/skills/ux-rules/scripts/contrast.py. Buttons get a
# fill of their own (control, a step off the card) and an outline, so they read as buttons in a grayscale screenshot;
# ink is 13:1 or more on control and control_hover, danger (Remove, Delete) 4.5:1 or more on card and hover.
THEMES = {
    "light": {
        "page": "#f3f3f1", "card": "#fcfcfb", "ink": "#0b0b0b", "ink2": "#52514e", "muted": "#6b6a65",
        "grid": "#e1e0d9", "border": "#dcdbd4", "accent": "#2368c0", "accent_ink": "#ffffff", "hover": "#ebeae5",
        "good": "#087a08", "warn": "#8a5f00", "bad": "#c03535", "select": "#dbe8f8",
        "control": "#f3f3f1", "control_hover": "#e7e6e0", "control_border": "#c9c8c0", "danger": "#c03535",
    },
    "dark": {
        "page": "#111110", "card": "#1a1a19", "ink": "#f0efec", "ink2": "#c3c2b7", "muted": "#898781",
        "grid": "#2c2c2a", "border": "#33332f", "accent": "#3987e5", "accent_ink": "#0b0b0b", "hover": "#252523",
        "good": "#0ca30c", "warn": "#fab219", "bad": "#e05252", "select": "#1f3a5c",
        "control": "#262624", "control_hover": "#30302d", "control_border": "#4a4945", "danger": "#ec6a6a",
    },
}

def system_theme() -> str:
    if IS_WINDOWS:
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
                return "light" if winreg.QueryValueEx(k, "AppsUseLightTheme")[0] else "dark"
        except OSError:
            pass
    return "light"


def dark_title_bar(window) -> None:
    """A dark title bar on Windows when the system uses the dark theme (DWMWA_USE_IMMERSIVE_DARK_MODE)."""
    if not (IS_WINDOWS and system_theme() == "dark"):
        return
    try:
        import ctypes

        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(ctypes.c_int(1)), 4)
    except (OSError, AttributeError):
        pass


def apply(root, theme: str | None = None) -> dict:
    """Style every ttk widget of root's interpreter for the system theme (or `theme`) and return its palette."""
    from tkinter import ttk

    t = THEMES[theme or system_theme()]
    s = ttk.Style(root)
    s.theme_use("clam")
    base = (FONT, 10)
    s.configure(".", background=t["page"], foreground=t["ink"], font=base, bordercolor=t["border"],
                lightcolor=t["card"], darkcolor=t["card"], troughcolor=t["page"], focuscolor=t["accent"])
    s.configure("Card.TFrame", background=t["card"])
    s.configure("TLabel", background=t["page"], foreground=t["ink"])
    for name, fg, font in (("", t["ink"], base), ("Muted", t["muted"], (FONT, 9)), ("Sub", t["ink2"], base),
                           ("Title", t["ink"], (FONT, 11, "bold")), ("Big", t["ink"], (FONT, 18, "bold"))):
        s.configure(f"Card.{name}.TLabel" if name else "Card.TLabel", background=t["card"], foreground=fg, font=font)
    s.configure("Card.Name.TLabel", background=t["card"], foreground=t["ink"], font=(FONT, 10, "bold"))
    s.configure("Head.TLabel", background=t["page"], foreground=t["ink"], font=(FONT, 16, "bold"))
    s.configure("HeadSub.TLabel", background=t["page"], foreground=t["ink2"])
    s.configure("Warn.TLabel", background=t["card"], foreground=t["warn"])
    s.configure("Bad.TLabel", background=t["card"], foreground=t["bad"])
    s.configure("Good.TLabel", background=t["card"], foreground=t["good"])
    s.configure("Card.Head.TLabel", background=t["card"], foreground=t["ink2"], font=(FONT, 9, "bold"))
    # A text field: the card's fill, the buttons' outline, and the 2 px accent ring on focus like the comboboxes.
    s.configure("TEntry", fieldbackground=t["card"], foreground=t["ink"], insertcolor=t["ink"], padding=4,
                bordercolor=t["control_border"], lightcolor=t["card"], darkcolor=t["card"])
    s.map("TEntry", bordercolor=[("focus", t["accent"])], lightcolor=[("focus", t["accent"])])
    # Keyboard focus: clam's dotted ring inside, plus a 2 px solid ring (clam draws a border only for a solid or
    # raised relief). Rings are accent on surfaces and ink or accent-ink on accent fills, 3:1 or more either way.
    s.configure("TButton", background=t["control"], foreground=t["ink"], padding=(10, 4), relief="solid", borderwidth=1,
                bordercolor=t["control_border"], lightcolor=t["control"], darkcolor=t["control"])
    s.map("TButton", background=[("disabled", t["card"]), ("active", t["control_hover"])],
          lightcolor=[("disabled", t["card"]), ("active", t["control_hover"])],
          darkcolor=[("disabled", t["card"]), ("active", t["control_hover"])],
          foreground=[("disabled", t["muted"])], bordercolor=[("focus", t["accent"]), ("disabled", t["border"])])
    s.configure("Accent.TButton", background=t["accent"], foreground=t["accent_ink"], bordercolor=t["accent"],
                lightcolor=t["accent"], darkcolor=t["accent"], focuscolor=t["accent_ink"])
    s.map("Accent.TButton", background=[("disabled", t["border"]), ("active", t["accent"])],
          lightcolor=[("disabled", t["border"]), ("active", t["accent"])],
          darkcolor=[("disabled", t["border"]), ("active", t["accent"])], bordercolor=[("focus", t["ink"])])
    # A destructive action (Remove, Delete model): outlined in the danger colour, never filled like the primary one.
    s.configure("Danger.TButton", background=t["card"], foreground=t["danger"], bordercolor=t["danger"],
                lightcolor=t["card"], darkcolor=t["card"])
    s.map("Danger.TButton", background=[("active", t["hover"])], lightcolor=[("active", t["hover"])],
          darkcolor=[("active", t["hover"])], foreground=[("disabled", t["muted"])], bordercolor=[("focus", t["ink"])])
    s.configure("Horizontal.TProgressbar", background=t["accent"], troughcolor=t["grid"], bordercolor=t["card"],
                lightcolor=t["accent"], darkcolor=t["accent"])
    s.configure("Seg.TRadiobutton", background=t["card"], foreground=t["ink2"], padding=(10, 3), indicatorrelief="flat", relief="flat")
    s.layout("Seg.TRadiobutton", [("Radiobutton.border", {"sticky": "nswe", "children": [("Radiobutton.padding", {"sticky": "nswe", "children": [
        ("Radiobutton.focus", {"sticky": "nswe", "children": [("Radiobutton.label", {"sticky": "nswe"})]})]})]})])
    s.map("Seg.TRadiobutton", background=[("selected", t["accent"]), ("active", t["hover"])], foreground=[("selected", t["accent_ink"])],
          relief=[("focus", "solid")], bordercolor=[("focus", "selected", t["ink"]), ("focus", t["accent"])],
          focuscolor=[("selected", t["accent_ink"])])
    for w in ("TCheckbutton",):
        s.configure(w, background=t["card"], foreground=t["ink"], indicatorbackground=t["card"], indicatorforeground=t["accent"], relief="flat")
        s.layout(w, [("Checkbutton.border", {"sticky": "nswe", "children": [("Checkbutton.padding", {"sticky": "nswe", "children": [
            ("Checkbutton.indicator", {"side": "left", "sticky": ""}),
            ("Checkbutton.focus", {"side": "left", "sticky": "w", "children": [("Checkbutton.label", {"sticky": "nswe"})]})]})]})])
        s.map(w, background=[("active", t["card"])], indicatorbackground=[("selected", t["card"])],
              foreground=[("disabled", t["muted"])], indicatorforeground=[("disabled", t["muted"])],
              relief=[("focus", "solid")], bordercolor=[("focus", t["accent"])])
    s.configure("Page.TCheckbutton", background=t["page"])
    s.map("Page.TCheckbutton", background=[("active", t["page"])])
    s.configure("TCombobox", fieldbackground=t["card"], background=t["card"], foreground=t["ink"], arrowcolor=t["ink2"], padding=3)
    # The field draws bordercolor outside and lightcolor inside: both on focus make the 2 px ring, since these
    # maps hide clam's own cue for a focused read-only box (its selected text).
    s.map("TCombobox", fieldbackground=[("readonly", t["card"])], foreground=[("readonly", t["ink"])],
          selectbackground=[("readonly", t["card"])], selectforeground=[("readonly", t["ink"])],
          bordercolor=[("focus", t["accent"])], lightcolor=[("focus", t["accent"])])
    root.option_add("*TCombobox*Listbox.background", t["card"])
    root.option_add("*TCombobox*Listbox.foreground", t["ink"])
    root.option_add("*TCombobox*Listbox.selectBackground", t["select"])
    root.option_add("*TCombobox*Listbox.selectForeground", t["ink"])
    s.configure("TNotebook", background=t["page"], borderwidth=0, tabmargins=(0, 0, 0, 0))
    s.configure("TNotebook.Tab", background=t["page"], foreground=t["ink2"], padding=(16, 7), borderwidth=0, font=(FONT, 10))
    s.map("TNotebook.Tab", background=[("selected", t["card"])], foreground=[("selected", t["ink"])],
          lightcolor=[("focus", "selected", t["accent"]), ("selected", t["card"])],
          bordercolor=[("focus", "selected", t["accent"]), ("selected", t["border"])], expand=[("selected", (0, 0, 0, 0))])
    s.configure("Treeview", background=t["card"], fieldbackground=t["card"], foreground=t["ink"], rowheight=26, borderwidth=0)
    s.map("Treeview", background=[("selected", t["select"])], foreground=[("selected", t["ink"])])
    s.configure("Treeview.Heading", background=t["card"], foreground=t["ink2"], relief="flat", font=(FONT, 9, "bold"), padding=(6, 4))
    s.map("Treeview.Heading", background=[("active", t["hover"])])
    s.configure("Vertical.TScrollbar", background=t["card"], troughcolor=t["page"], arrowcolor=t["ink2"], bordercolor=t["page"])

    return t
