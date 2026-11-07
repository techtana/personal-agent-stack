"""Parse hotkey strings such as "ctrl+alt+space" into Win32 RegisterHotKey modifiers and a virtual-key code."""
from __future__ import annotations

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN = 0x1, 0x2, 0x4, 0x8
MODIFIERS = {"ctrl": MOD_CONTROL, "control": MOD_CONTROL, "alt": MOD_ALT, "shift": MOD_SHIFT,
             "win": MOD_WIN, "windows": MOD_WIN, "super": MOD_WIN}
KEYS = {
    "space": 0x20, "enter": 0x0D, "tab": 0x09, "esc": 0x1B, "escape": 0x1B, "pause": 0x13, "scrolllock": 0x91,
    "insert": 0x2D, "delete": 0x2E, "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27, "apps": 0x5D, "menu": 0x5D,
    "`": 0xC0, "grave": 0xC0, "backtick": 0xC0, ";": 0xBA, "=": 0xBB, ",": 0xBC, "-": 0xBD, ".": 0xBE, "/": 0xBF,
    "[": 0xDB, "\\": 0xDC, "]": 0xDD, "'": 0xDE,
}
KEYS.update({f"f{n}": 0x6F + n for n in range(1, 25)})  # F1 = 0x70
VK_ESCAPE = 0x1B

# Offered in the tray's Settings tab; free in Windows 11, Logseq, VS Code, Chrome and Notion by default (Ctrl+Alt+D is
# "insert endnote" in Word). Ctrl+Alt+Space is the Claude desktop app's quick entry; Ctrl+Shift+Space is parameter hints
# in VS Code; Ctrl+Alt+V is Paste Special in Office; F9 toggles a breakpoint in VS Code.
CHOICES = ["ctrl+alt+d", "ctrl+alt+h", "alt+`", "win+alt+h", "ctrl+alt+space", "ctrl+shift+space", "pause", "scrolllock"]


class HotkeyError(ValueError):
    pass


def parse(text: str) -> tuple[int, int]:
    """("ctrl+alt+space") -> (MOD_CONTROL | MOD_ALT, 0x20). A single key without modifiers is allowed only for keys
    that are not typed (function keys, Pause, Scroll Lock, Insert), so a plain letter cannot swallow typing."""
    parts = [p.strip().lower() for p in (text or "").replace(" ", "").split("+") if p.strip()]
    if not parts:
        raise HotkeyError("empty hotkey")
    mods = 0
    for p in parts[:-1]:
        if p not in MODIFIERS:
            raise HotkeyError(f"{p!r} is not a modifier (use ctrl, alt, shift or win)")
        mods |= MODIFIERS[p]
    key = parts[-1]
    if key in MODIFIERS:
        raise HotkeyError("a hotkey needs a key after the modifiers (Windows cannot register a modifier on its own)")
    if len(key) == 1 and (key.isalpha() or key.isdigit()):
        vk = ord(key.upper())
    elif key in KEYS:
        vk = KEYS[key]
    else:
        raise HotkeyError(f"unknown key {key!r}")
    typed = len(key) == 1 or key in ("space", "enter", "tab", "esc", "escape", "delete", "up", "down", "left", "right",
                                      "home", "end", "pageup", "pagedown")
    if not mods & (MOD_CONTROL | MOD_ALT | MOD_WIN) and typed:
        raise HotkeyError(f"{text!r} would swallow normal typing; add ctrl, alt or win")
    return mods, vk


def label(text: str) -> str:
    """'ctrl+alt+space' -> 'Ctrl+Alt+Space'."""
    return "+".join(p.strip().upper() if len(p.strip()) <= 1 else p.strip().capitalize() for p in (text or "").split("+"))
