"""Read the text selected in the focused app, and later paste new text over it, through the clipboard.

Windows has no common way to read another program's selection, so this does what you would do by hand: press Ctrl+C,
read the clipboard, and put back what you had copied before. Replacing presses Ctrl+C once more first and pastes only
when the same text is still selected in the same window; if you clicked elsewhere or switched windows while the
model worked, the new text goes to the clipboard instead and nothing in the document changes.

Both functions take the Win32 helpers as arguments (winsys and its Clipboard in the app, fakes in the tests). Run them
on the inserter thread, one at a time, so they never interleave with a dictation's paste.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass

# Ctrl+C in a terminal stops the running program when nothing is selected.
TERMINALS = {"windowsterminal.exe", "openconsole.exe", "conhost.exe", "cmd.exe", "powershell.exe", "pwsh.exe",
             "mintty.exe", "alacritty.exe", "wezterm-gui.exe", "putty.exe", "kitty.exe", "hyper.exe", "tabby.exe",
             "conemu.exe", "conemu64.exe", "mobaxterm.exe", "wsl.exe", "wslhost.exe", "warp.exe"}
# Editors with a terminal panel inside (VS Code, Cursor, JetBrains IDEs, Visual Studio): there the copy uses Ctrl+Insert,
# which their editors treat as Copy and which cannot stop a program running in the panel.
COPY_WITH_CTRL_INSERT = {"code.exe", "code - insiders.exe", "cursor.exe", "windsurf.exe", "zed.exe", "devenv.exe",
                         "idea64.exe", "pycharm64.exe", "webstorm64.exe", "rider64.exe", "clion64.exe", "goland64.exe",
                         "phpstorm64.exe", "rubymine64.exe", "datagrip64.exe", "studio64.exe", "fleet.exe"}
# Editors that copy the whole line when nothing is selected mark the clipboard: Scintilla (Notepad++) and Visual
# Studio with these formats, VS Code inside Chromium's custom data ("isFromEmptySelection").
LINE_COPY_FORMATS = {"MSDEVLineSelect", "VisualStudioEditorOperationsLineCutCopyClipboardTag"}
# The HTML of a copy that holds more than text. Pasting plain text over it would delete the picture or table.
OBJECTS = re.compile(r"<(img|table|svg|video|iframe|object|embed)\b", re.I)
_FRAGMENT = re.compile(r"<!--\s*StartFragment\s*-->(.*)<!--\s*EndFragment\s*-->", re.I | re.S)
NOTHING_SELECTED = "Select some text first, then try again."


class SelectionError(Exception):
    """Why the selection could not be read; title and hint go into the button's bubble."""

    def __init__(self, title: str, hint: str = "") -> None:
        super().__init__(title)
        self.title, self.hint = title, hint


@dataclass
class Selection:
    text: str
    target: int
    app: str
    window: str


def normalise(text: str) -> str:
    return " ".join((text or "").split())


def _front(ws, target: int) -> None:
    """Make sure `target` has the keyboard focus; a menu of ours may have taken it for a moment."""
    if ws.root_window(ws.foreground()) == target:
        return
    ws.activate(target)
    deadline = time.monotonic() + 0.6
    while ws.root_window(ws.foreground()) != target:
        if time.monotonic() > deadline:
            raise SelectionError("The app you came from is not in front", "Click into the text and try again.")
        time.sleep(0.03)
    time.sleep(0.12)  # let the window restore its own focus and selection


def _wait_copy(ws, before: int, wait: float) -> bool:
    """True once the clipboard changed after our Ctrl+C and the app has closed it again."""
    deadline = time.monotonic() + wait
    while ws.sequence() == before:
        if time.monotonic() > deadline:
            return False
        time.sleep(0.02)
    deadline = time.monotonic() + 0.8
    while ws.clipboard_busy() and time.monotonic() < deadline:
        time.sleep(0.02)
    return True


def fragment(html: str) -> str:
    """The selected part of CF_HTML. Around it Word and Chromium put context (a selection inside a table cell comes with
    the table's tags), which must not count as a selected table."""
    m = _FRAGMENT.search(html or "")
    return m.group(1) if m else (html or "")


def line_copy(data: dict) -> bool:
    if set(data.get("formats") or ()) & LINE_COPY_FORMATS:
        return True
    return '"isFromEmptySelection":true' in (data.get("custom") or "").replace(" ", "")


PURPOSES = {"refine": ("Refine", "refined"), "read": ("Read aloud", "read aloud")}


def capture(ws, clip, target: int, *, elevated: bool, copy_wait: float = 2.0, purpose: str = "refine") -> Selection:
    """The text selected in `target`, read with Ctrl+C; your clipboard is put back right after. Raises SelectionError.
    purpose "read" (read aloud) also takes a selection with pictures or tables in it: only its text is used."""
    what, done = PURPOSES.get(purpose, PURPOSES["refine"])
    if not target:
        raise SelectionError("No app window to read from", f"Click into the text you want {done} first.")
    if not ws.wait_modifiers_released(2.0):
        raise SelectionError("Keys are still held down", "Let go of Ctrl, Alt and Shift, then try again.")
    _front(ws, target)
    pid = ws.window_pid(target)
    app = ws.process_name(pid)
    if app in TERMINALS:
        raise SelectionError(f"{what} does not work in a terminal", "Ctrl+C there could stop the program that runs in it.")
    if not elevated and ws.is_elevated(pid) is not False:
        raise SelectionError(f"{app or 'That window'} may run as administrator",
                             "Windows blocks simulated keys there, so its selection cannot be read.")
    try:
        snap = clip.snapshot()
    except OSError:
        raise SelectionError("The clipboard is in use by another program", "Try again in a moment.") from None
    if snap is None:
        raise SelectionError("The clipboard holds more than 64 MB",
                             f"Copy something small first, so {what.lower()} does not lose what is on it.")
    before = ws.sequence()
    if not ws.send_copy(ctrl_insert=app in COPY_WITH_CTRL_INSERT):
        raise SelectionError("Windows refused the simulated keys", "Try again, or copy and paste the text yourself.")
    if not _wait_copy(ws, before, copy_wait):
        raise SelectionError("Nothing selected", NOTHING_SELECTED)  # the clipboard did not change: nothing to restore
    copied = ws.sequence()
    try:
        data = clip.read()
    finally:
        if ws.sequence() == copied:
            clip.restore(snap)
    if line_copy(data):
        raise SelectionError("Nothing selected", "This editor copied the whole line. " + NOTHING_SELECTED)
    text = data.get("text") or ""
    if not text.strip():
        raise SelectionError("The selection has no text", f"Pictures and other objects cannot be {done}.")
    if purpose != "read" and OBJECTS.search(fragment(data.get("html") or "")):
        raise SelectionError("The selection includes a picture or a table",
                             "Refine would replace it with plain text. Select text only.")
    return Selection(text, target, app, ws.window_title(target))


def replace(ws, clip, sel: Selection, new_text: str, *, ours=lambda hwnd: False, copy_wait: float = 1.0,
            settle: float = 1.0) -> tuple[str, str]:
    """Paste `new_text` over the selection if the same text is still selected in the same window.
    Returns (outcome, detail): "replaced"; "copied" when the new text went to the clipboard instead; "skipped" when
    nothing was touched. It never pulls the focus back from another app you moved to while the model worked, only
    from a window of ours (`ours(hwnd)`: a menu, the bubble, the history window)."""

    def to_clipboard(why: str) -> tuple[str, str]:
        clip.set_text(new_text, hide=False)  # you will paste it yourself, so clipboard history may keep it
        return "copied", why + " The new text is on the clipboard: select the old text and press Ctrl+V."

    switched = "You switched to another window, so nothing was replaced."
    if not ws.wait_modifiers_released(2.0):
        return to_clipboard("Keys were still held down, so nothing was replaced.")
    front = ws.root_window(ws.foreground())
    if front != sel.target:
        if not ours(front):
            return to_clipboard(switched)
        try:
            _front(ws, sel.target)
        except SelectionError:
            return to_clipboard(switched)
    try:
        snap = clip.snapshot()
    except OSError:
        snap = None
    if snap is None:  # what you copied meanwhile could not be saved and put back: leave the clipboard alone
        return "skipped", ("Your clipboard is busy or holds more than 64 MB, so nothing was replaced. The new text is "
                           "in the refine history.")
    before = ws.sequence()
    if not ws.send_copy(ctrl_insert=sel.app in COPY_WITH_CTRL_INSERT):
        return to_clipboard("Windows refused the simulated keys, so nothing was replaced.")
    gone = "The text is no longer selected, so nothing was replaced."
    if not _wait_copy(ws, before, copy_wait):
        return to_clipboard(gone)
    data = clip.read()
    if line_copy(data):
        return to_clipboard(gone)  # the caret is on that line: pasting would add a second copy, not replace it
    if normalise(data.get("text") or "") != normalise(sel.text):
        return to_clipboard("The selection changed while the model worked, so nothing was replaced.")
    if ws.root_window(ws.foreground()) != sel.target:
        return to_clipboard(switched)
    seq = clip.set_text(new_text)  # hidden from clipboard history
    ok = ws.send_paste(shift_insert=sel.app in ws.SHIFT_INSERT_APPS)
    # The app reads the clipboard while it handles Ctrl+V; Electron apps and Word can take a while.
    time.sleep(settle)
    deadline = time.monotonic() + 1.0
    while ws.clipboard_busy() and time.monotonic() < deadline:
        time.sleep(0.05)
    if not ok:
        return to_clipboard("Windows refused the simulated keys.")
    if ws.sequence() == seq:
        clip.restore(snap)
    return "replaced", f"{len(new_text)} characters into {sel.app or 'the window'}"
