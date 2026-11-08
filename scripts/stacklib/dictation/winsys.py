"""Windows plumbing through ctypes: global hotkeys, key state, the clipboard, simulated input and window styles.

Text goes into the focused app in one of two ways:
  - paste: save the clipboard, put the text on it, press Ctrl+V, restore the clipboard half a second later (unless
    something else changed it meanwhile). Fast for long text and any script; our own text is kept out of clipboard
    history and cloud clipboard.
  - type: SendInput with KEYEVENTF_UNICODE, one UTF-16 unit at a time; Enter for line breaks. For apps that block
    paste. Editors that auto-pair brackets (Logseq) may double a typed "(" or "[".
Windows does not let a normal program send input to a program running as administrator (UIPI); insert() reports that
case instead of failing silently.
"""
from __future__ import annotations

import ctypes
import queue
import threading
import time
from ctypes import wintypes
from typing import Callable

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

ULONG_PTR = ctypes.c_size_t
LRESULT = ctypes.c_ssize_t
MOD_NOREPEAT = 0x4000
WM_HOTKEY, WM_QUIT, WM_APP, WM_USER = 0x0312, 0x0012, 0x8000, 0x0400
PM_NOREMOVE = 0
VK_SHIFT, VK_CONTROL, VK_MENU, VK_LWIN, VK_RWIN = 0x10, 0x11, 0x12, 0x5B, 0x5C
VK_RETURN, VK_TAB, VK_INSERT, VK_V = 0x0D, 0x09, 0x2D, 0x56
INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP, KEYEVENTF_UNICODE = 0x1, 0x2, 0x4
INJECTED_TAG = 0x0D1C7A7E  # dwExtraInfo on our own key events
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
# Clipboard formats that are GDI handles, not memory blocks; they cannot be copied byte for byte. Windows synthesises
# CF_BITMAP from CF_DIB, so a saved bitmap survives through its CF_DIB copy.
GDI_FORMATS = {2, 3, 9, 14, 0x80, 0x82, 0x83, 0x8E}
GWL_EXSTYLE = -20
WS_EX_TOPMOST, WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = 0x00000008, 0x00000080, 0x08000000
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE, SWP_FRAMECHANGED = 0x1, 0x2, 0x10, 0x20
HWND_TOPMOST = -1
GA_ROOT = 2
# Terminals where Ctrl+V does not paste (mintty, the Git Bash window) take Shift+Insert.
SHIFT_INSERT_APPS = {"mintty.exe"}


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


def _sig(fn, args, res=None):
    fn.argtypes = args
    if res is not None:
        fn.restype = res
    return fn


_sig(user32.RegisterHotKey, (wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT), wintypes.BOOL)
_sig(user32.UnregisterHotKey, (wintypes.HWND, ctypes.c_int), wintypes.BOOL)
_sig(user32.GetMessageW, (ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT), ctypes.c_int)
_sig(user32.PeekMessageW, (ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT), wintypes.BOOL)
_sig(user32.PostThreadMessageW, (wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM), wintypes.BOOL)
_sig(user32.GetAsyncKeyState, (ctypes.c_int,), ctypes.c_short)
_sig(user32.SendInput, (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int), wintypes.UINT)
_sig(user32.GetForegroundWindow, (), wintypes.HWND)
_sig(user32.SetForegroundWindow, (wintypes.HWND,), wintypes.BOOL)
_sig(user32.GetAncestor, (wintypes.HWND, wintypes.UINT), wintypes.HWND)
_sig(user32.GetWindowThreadProcessId, (wintypes.HWND, ctypes.POINTER(wintypes.DWORD)), wintypes.DWORD)
_sig(user32.OpenClipboard, (wintypes.HWND,), wintypes.BOOL)
_sig(user32.CloseClipboard, (), wintypes.BOOL)
_sig(user32.EmptyClipboard, (), wintypes.BOOL)
_sig(user32.EnumClipboardFormats, (wintypes.UINT,), wintypes.UINT)
_sig(user32.GetClipboardData, (wintypes.UINT,), wintypes.HANDLE)
_sig(user32.SetClipboardData, (wintypes.UINT, wintypes.HANDLE), wintypes.HANDLE)
_sig(user32.RegisterClipboardFormatW, (wintypes.LPCWSTR,), wintypes.UINT)
_sig(user32.GetClipboardSequenceNumber, (), wintypes.DWORD)
_sig(user32.GetOpenClipboardWindow, (), wintypes.HWND)
_sig(user32.CreateWindowExW, (wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_int,
                              ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND, wintypes.HMENU,
                              wintypes.HINSTANCE, wintypes.LPVOID), wintypes.HWND)
_sig(user32.DestroyWindow, (wintypes.HWND,), wintypes.BOOL)
_sig(user32.SetWindowPos, (wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                           wintypes.UINT), wintypes.BOOL)
_GetWindowLong = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
_SetWindowLong = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
_sig(_GetWindowLong, (wintypes.HWND, ctypes.c_int), ctypes.c_ssize_t)
_sig(_SetWindowLong, (wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t), ctypes.c_ssize_t)
_sig(kernel32.GlobalAlloc, (wintypes.UINT, ctypes.c_size_t), wintypes.HGLOBAL)
_sig(kernel32.GlobalLock, (wintypes.HGLOBAL,), wintypes.LPVOID)
_sig(kernel32.GlobalUnlock, (wintypes.HGLOBAL,), wintypes.BOOL)
_sig(kernel32.GlobalSize, (wintypes.HGLOBAL,), ctypes.c_size_t)
_sig(kernel32.GlobalFree, (wintypes.HGLOBAL,), wintypes.HGLOBAL)
_sig(kernel32.GetCurrentThreadId, (), wintypes.DWORD)
_sig(kernel32.OpenProcess, (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD), wintypes.HANDLE)
_sig(kernel32.CloseHandle, (wintypes.HANDLE,), wintypes.BOOL)
_sig(kernel32.QueryFullProcessImageNameW, (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                           ctypes.POINTER(wintypes.DWORD)), wintypes.BOOL)
_sig(kernel32.GetCurrentProcess, (), wintypes.HANDLE)
_sig(advapi32.OpenProcessToken, (wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)), wintypes.BOOL)
_sig(advapi32.GetTokenInformation, (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
                                    ctypes.POINTER(wintypes.DWORD)), wintypes.BOOL)


# ---------------------------------------------------------------- hotkeys

class HotkeyThread(threading.Thread):
    """Owns RegisterHotKey registrations (they belong to the thread that made them) and its message loop.
    register()/unregister() may be called from any thread; on_hotkey(name) runs on this thread, so keep it short."""

    def __init__(self, on_hotkey: Callable[[str], None]) -> None:
        super().__init__(name="dictation-hotkeys", daemon=True)
        self.on_hotkey = on_hotkey
        self.thread_id = 0
        self.ready = threading.Event()
        self.requests: queue.Queue = queue.Queue()
        self.ids: dict[str, int] = {}
        self.names: dict[int, str] = {}
        self._next = 1

    def run(self) -> None:
        msg = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, WM_USER, WM_USER, PM_NOREMOVE)  # create the message queue
        self.thread_id = kernel32.GetCurrentThreadId()
        self.ready.set()
        while True:
            r = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if r in (0, -1):
                break
            if msg.message == WM_HOTKEY:
                name = self.names.get(int(msg.wParam))
                if name:
                    try:
                        self.on_hotkey(name)
                    except Exception as e:  # noqa: BLE001 - never let a handler end the hotkey loop
                        print(f"[dictation] hotkey handler failed: {e}", flush=True)
            elif msg.message == WM_APP:
                self._serve()
        for hid in list(self.names):
            user32.UnregisterHotKey(None, hid)

    def _serve(self) -> None:
        while True:
            try:
                op, name, mods, vk, reply = self.requests.get_nowait()
            except queue.Empty:
                return
            ok, err = True, ""
            if name in self.ids:
                user32.UnregisterHotKey(None, self.ids[name])
                self.names.pop(self.ids.pop(name), None)
            if op == "register":
                hid = self._next
                self._next += 1
                if user32.RegisterHotKey(None, hid, mods | MOD_NOREPEAT, vk):
                    self.ids[name], self.names[hid] = hid, name
                else:
                    ok, err = False, ctypes.FormatError(ctypes.get_last_error()).strip()
            reply.put((ok, err))

    def _request(self, op: str, name: str, mods: int = 0, vk: int = 0) -> tuple[bool, str]:
        self.ready.wait(5)
        reply: queue.Queue = queue.Queue()
        self.requests.put((op, name, mods, vk, reply))
        user32.PostThreadMessageW(self.thread_id, WM_APP, 0, 0)
        try:
            return reply.get(timeout=3)
        except queue.Empty:
            return False, "the hotkey thread did not answer"

    def register(self, name: str, mods: int, vk: int) -> tuple[bool, str]:
        return self._request("register", name, mods, vk)

    def unregister(self, name: str) -> None:
        self._request("unregister", name)

    def stop(self) -> None:
        if self.thread_id:
            user32.PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0)


def key_down(vk: int) -> bool:
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def modifiers_down() -> bool:
    return any(key_down(vk) for vk in (VK_SHIFT, VK_CONTROL, VK_MENU, VK_LWIN, VK_RWIN))


def wait_modifiers_released(timeout: float = 2.0) -> bool:
    """Wait until Ctrl, Alt, Shift and Win are up, so a pasted Ctrl+V is not read as Ctrl+Alt+V."""
    deadline = time.monotonic() + timeout
    while modifiers_down():
        if time.monotonic() > deadline:
            return False
        time.sleep(0.02)
    return True


# ---------------------------------------------------------------- windows and processes

def foreground() -> int:
    return int(user32.GetForegroundWindow() or 0)


def activate(hwnd: int) -> bool:
    """Bring a window to the front. Windows allows it because this process just received the user's click."""
    return bool(user32.SetForegroundWindow(hwnd)) if hwnd else False


def root_window(hwnd: int) -> int:
    return int(user32.GetAncestor(hwnd, GA_ROOT) or hwnd) if hwnd else 0


def window_pid(hwnd: int) -> int:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def process_name(pid: int) -> str:
    handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(buf))
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return buf.value.rsplit("\\", 1)[-1].lower()
        return ""
    finally:
        kernel32.CloseHandle(handle)


def _elevated(process: int) -> bool | None:
    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(process, 0x0008, ctypes.byref(token)):  # TOKEN_QUERY
        return None
    try:
        value, size = wintypes.DWORD(), wintypes.DWORD()
        if not advapi32.GetTokenInformation(token, 20, ctypes.byref(value), ctypes.sizeof(value), ctypes.byref(size)):
            return None  # 20 = TokenElevation
        return bool(value.value)
    finally:
        kernel32.CloseHandle(token)


def is_elevated(pid: int) -> bool | None:
    """True when the process runs as administrator; None when Windows will not say (often: it is elevated)."""
    handle = kernel32.OpenProcess(0x1000, False, pid)
    if not handle:
        return None
    try:
        return _elevated(handle)
    finally:
        kernel32.CloseHandle(handle)


def self_elevated() -> bool:
    return bool(_elevated(kernel32.GetCurrentProcess()))


def make_overlay(hwnd: int) -> None:
    """Keep a window on top, out of the taskbar and Alt+Tab, and never activated by a click, so clicking the button
    leaves the keyboard focus (and the caret) in the app you are dictating into."""
    ex = _GetWindowLong(hwnd, GWL_EXSTYLE)
    _SetWindowLong(hwnd, GWL_EXSTYLE, ex | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST)
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED)


_WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
_sig(user32.EnumThreadWindows, (wintypes.DWORD, _WNDENUMPROC, wintypes.LPARAM), wintypes.BOOL)
_sig(user32.GetClassNameW, (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int), ctypes.c_int)
_sig(user32.IsWindowVisible, (wintypes.HWND,), wintypes.BOOL)
_sig(user32.GetWindowRect, (wintypes.HWND, ctypes.POINTER(wintypes.RECT)), wintypes.BOOL)
_sig(user32.GetCursorPos, (ctypes.POINTER(wintypes.POINT),), wintypes.BOOL)
_sig(user32.EndMenu, (), wintypes.BOOL)


def cursor_pos() -> tuple[int, int]:
    pt = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def popup_menu_rects() -> list[tuple[int, int, int, int]]:
    """Screen rectangles (left, top, right, bottom) of the popup menus (class #32768) open on this thread: a menu
    from tk_popup and any submenu it opened."""
    rects: list[tuple[int, int, int, int]] = []
    name = ctypes.create_unicode_buffer(16)

    def visit(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd) and user32.GetClassNameW(hwnd, name, 16) and name.value == "#32768":
            r = wintypes.RECT()
            if user32.GetWindowRect(hwnd, ctypes.byref(r)):
                rects.append((r.left, r.top, r.right, r.bottom))
        return True

    user32.EnumThreadWindows(kernel32.GetCurrentThreadId(), _WNDENUMPROC(visit), 0)
    return rects


def end_menu() -> None:
    """Close the menu this thread is tracking (tk_popup's native loop returns, as if Esc was pressed)."""
    user32.EndMenu()


def round_corners(hwnd: int) -> None:
    """Windows 11 draws rounded, anti-aliased corners and a shadow (DWMWA_WINDOW_CORNER_PREFERENCE = round)."""
    try:
        dwm = ctypes.WinDLL("dwmapi")
        value = ctypes.c_int(2)
        dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), 33, ctypes.byref(value), ctypes.sizeof(value))
    except OSError:
        pass


def set_dpi_aware() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # sharp text on scaled displays; before Tk() (as installer.py)
    except (AttributeError, OSError):
        pass


# ---------------------------------------------------------------- input

def _key(vk: int = 0, scan: int = 0, flags: int = 0) -> INPUT:
    inp = INPUT(type=INPUT_KEYBOARD)
    inp.ki = KEYBDINPUT(vk, scan, flags, 0, INJECTED_TAG)
    return inp


def _send(events: list[INPUT]) -> int:
    if not events:
        return 0
    arr = (INPUT * len(events))(*events)
    return user32.SendInput(len(events), arr, ctypes.sizeof(INPUT))


def send_paste(shift_insert: bool = False) -> bool:
    if shift_insert:
        seq = [_key(VK_SHIFT), _key(VK_INSERT, flags=KEYEVENTF_EXTENDEDKEY),
               _key(VK_INSERT, flags=KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP), _key(VK_SHIFT, flags=KEYEVENTF_KEYUP)]
    else:
        seq = [_key(VK_CONTROL), _key(VK_V), _key(VK_V, flags=KEYEVENTF_KEYUP), _key(VK_CONTROL, flags=KEYEVENTF_KEYUP)]
    return _send(seq) == len(seq)


def type_text(text: str, chunk: int = 40) -> bool:
    """Type text as Unicode key events; line breaks become Enter and tabs Tab."""
    events: list[INPUT] = []
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    for ch in text:
        if ch == "\n":
            events += [_key(VK_RETURN), _key(VK_RETURN, flags=KEYEVENTF_KEYUP)]
            continue
        if ch == "\t":
            events += [_key(VK_TAB), _key(VK_TAB, flags=KEYEVENTF_KEYUP)]
            continue
        data = ch.encode("utf-16-le")
        for i in range(0, len(data), 2):
            unit = int.from_bytes(data[i:i + 2], "little")
            events += [_key(0, unit, KEYEVENTF_UNICODE), _key(0, unit, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)]
    ok = True
    for i in range(0, len(events), chunk * 2):
        part = events[i:i + chunk * 2]
        ok &= _send(part) == len(part)
        time.sleep(0.005)  # let the target's message loop keep up
    return ok


# ---------------------------------------------------------------- clipboard

class _Clipboard:
    """Open the clipboard with a fresh hidden owner window and destroy that window afterwards. The owner gets
    WM_DESTROYCLIPBOARD, sent synchronously, whenever another program empties the clipboard; a window of ours that
    outlived the call, on a thread that does not pump messages, could make that program's copy hang. The data stays on
    the clipboard after the owner is gone (no delayed rendering is used). pyperclip does the same."""

    def __enter__(self):
        self.hwnd = user32.CreateWindowExW(0, "STATIC", None, 0, 0, 0, 0, 0, None, None, None, None)
        for _ in range(50):  # another program may hold it for a moment
            if user32.OpenClipboard(self.hwnd):
                return self
            time.sleep(0.02)
        if self.hwnd:
            user32.DestroyWindow(self.hwnd)
        raise OSError("the clipboard is in use by another program")

    def __exit__(self, *exc) -> None:
        user32.CloseClipboard()
        if self.hwnd:
            user32.DestroyWindow(self.hwnd)


def _put(fmt: int, data: bytes) -> None:
    handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, max(len(data), 1))
    if not handle:
        raise MemoryError("GlobalAlloc failed")
    ptr = kernel32.GlobalLock(handle)
    ctypes.memmove(ptr, data, len(data))
    kernel32.GlobalUnlock(handle)
    if not user32.SetClipboardData(fmt, handle):
        kernel32.GlobalFree(handle)


def _hide_from_history() -> None:
    """Keep this content out of Win+V clipboard history and cloud clipboard."""
    _put(user32.RegisterClipboardFormatW("ExcludeClipboardContentFromMonitorProcessing"), b"\0")
    _put(user32.RegisterClipboardFormatW("CanIncludeInClipboardHistory"), (0).to_bytes(4, "little"))
    _put(user32.RegisterClipboardFormatW("CanUploadToCloudClipboard"), (0).to_bytes(4, "little"))


class Clipboard:
    """Clipboard access. Each operation opens the clipboard with its own short-lived owner window (EmptyClipboard with
    no owner window makes SetClipboardData fail on some systems); see _Clipboard."""

    def close(self) -> None:
        pass

    def snapshot(self, limit: int = 64 << 20) -> list[tuple[int, bytes]] | None:
        """Every memory-block format on the clipboard, or None when it holds more than `limit` bytes."""
        items: list[tuple[int, bytes]] = []
        total = 0
        with _Clipboard():
            fmt = 0
            while True:
                fmt = user32.EnumClipboardFormats(fmt)
                if not fmt:
                    break
                if fmt in GDI_FORMATS:
                    continue
                handle = user32.GetClipboardData(fmt)
                size = kernel32.GlobalSize(handle) if handle else 0
                if not size:
                    continue
                total += size
                if total > limit:
                    return None
                ptr = kernel32.GlobalLock(handle)
                if not ptr:
                    continue
                try:
                    items.append((fmt, ctypes.string_at(ptr, size)))
                finally:
                    kernel32.GlobalUnlock(handle)
        return items

    def restore(self, items: list[tuple[int, bytes]]) -> None:
        with _Clipboard():
            user32.EmptyClipboard()
            for fmt, data in items:
                _put(fmt, data)
            if items:
                _hide_from_history()  # it is already in the history from when it was first copied

    def set_text(self, text: str, hide: bool = True) -> int:
        """Put text on the clipboard; returns the clipboard sequence number afterwards."""
        with _Clipboard():
            user32.EmptyClipboard()
            _put(CF_UNICODETEXT, (text + "\0").encode("utf-16-le"))
            if hide:
                _hide_from_history()
        return int(user32.GetClipboardSequenceNumber())

    def text(self) -> str:
        with _Clipboard():
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                return ""
            ptr = kernel32.GlobalLock(handle)
            try:
                return ctypes.wstring_at(ptr) if ptr else ""
            finally:
                kernel32.GlobalUnlock(handle)


def sequence() -> int:
    return int(user32.GetClipboardSequenceNumber())


def clipboard_busy() -> bool:
    """True while some window has the clipboard open (for example the target, reading what we pasted)."""
    return bool(user32.GetOpenClipboardWindow())
