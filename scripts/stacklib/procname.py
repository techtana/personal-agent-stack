"""PAS-<Name> program names for every process the stack runs, so Task Manager tells them apart from other Pythons.

Windows names a process after its .exe file, and Task Manager's Processes tab shows the description and icon stored
inside that file. Every service here is a Python interpreter, so all of them used to read "Python" (or python.exe).

`named(python, key)` returns `<venv>\\pas\\PAS-<Name>.exe`: a copy of the venv's base interpreter (python.exe or
pythonw.exe from pyvenv.cfg's `home`) next to the DLLs it loads. Python finds `<venv>\\pyvenv.cfg` one folder up and
runs as that venv, exactly as the venv's own Scripts\\python.exe would, but in one process instead of a launcher plus
a child interpreter, and under its own name (Details tab, tasklist, Resource Monitor, the tray's Resources tab).

The icon and the "PAS-<Name>" description in the Processes tab need resources written into the copy, which breaks its
Authenticode signature. Smart App Control refuses unsigned programs (VerifiedAndReputablePolicyState 1, and 2 may turn
into 1 later), so the copy is branded only where Smart App Control is off. Elsewhere it stays byte-identical to the
signed original and keeps running. A branded copy that is refused anyway (an App Control policy) is replaced by a
signed one: `mark_blocked`, called by the service starters, which then retry with the original command.

AGENT_STACK_PROCESS_NAMES=0 turns all of this off. Linux and macOS keep their interpreters (no copies).
"""
from __future__ import annotations

import ctypes
import os
import shutil
import struct
import threading
from pathlib import Path

from . import IS_WINDOWS, REPO, warn

PREFIX = "PAS-"
# One name per process the stack starts. Services use their services.SERVICE_ORDER id (tests check every one is here).
NAMES = {
    "tray": "PAS-Tray",
    "phoenix": "PAS-Phoenix",
    "litellm": "PAS-LiteLLM",
    "orchestrator": "PAS-Orchestrator",
    "comfyui": "PAS-ComfyUI",
    "kokoro": "PAS-Kokoro",
    "open_webui": "PAS-OpenWebUI",
    "dictation": "PAS-VoiceTyping",
    "recordings": "PAS-Recordings",   # the Whisper MCP server Claude Desktop starts
    "supervisor": "PAS-Supervisor",   # `stack.py run <svc>` under Task Scheduler
    "installer": "PAS-Installer",     # the setup worker behind install.cmd
}
FOLDER = "pas"            # <venv>\pas holds the copies
BLOCKED = "signed-only"   # marker file in that folder: never brand copies there again
BRAND_VERSION = 1         # bump when the branding (icon, version strings) changes, so copies are rebuilt
ICON_FILE = REPO / ".run" / "PAS.ico"

_lock = threading.Lock()
_warned: set[str] = set()


def enabled() -> bool:
    return IS_WINDOWS and os.environ.get("AGENT_STACK_PROCESS_NAMES", "1").strip().lower() not in ("0", "false", "no", "off")


def name_of(key: str) -> str:
    return NAMES[key]


def is_named(exe: str | os.PathLike) -> bool:
    return Path(exe).name.upper().startswith(PREFIX)


def smart_app_control_state() -> int | None:
    """0 off, 1 on, 2 evaluation; None when Windows does not report it (no Smart App Control on this system)."""
    if not IS_WINDOWS:
        return None
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\CI\Policy") as k:
            return int(winreg.QueryValueEx(k, "VerifiedAndReputablePolicyState")[0])
    except (OSError, ValueError):
        return None


def branding_allowed(folder: Path | None = None) -> bool:
    """Icon and description may be written into copies: Smart App Control is off (or absent) and no copy in `folder`
    was refused before. Evaluation mode counts as on: Windows may switch it on without asking."""
    if not IS_WINDOWS or os.environ.get("AGENT_STACK_PROCESS_ICON", "1").strip().lower() in ("0", "false", "no", "off"):
        return False
    if folder is not None and (folder / BLOCKED).exists():
        return False
    return smart_app_control_state() in (None, 0)


def _venv_home(venv: Path) -> tuple[Path | None, str]:
    """(base interpreter folder, Python version) from a venv's pyvenv.cfg."""
    home, version = None, ""
    try:
        for line in (venv / "pyvenv.cfg").read_text(encoding="utf-8", errors="replace").splitlines():
            key, _, value = line.partition("=")
            key, value = key.strip().lower(), value.strip()
            if key == "home" and value:
                home = Path(value)
            elif key in ("version_info", "version") and not version:
                version = value
    except OSError:
        pass
    return home, version


def _stamp(src: Path, branded: bool) -> str:
    st = src.stat()
    return f"{src}|{st.st_size}|{st.st_mtime_ns}|{'branded' if branded else 'signed'}|{BRAND_VERSION}"


def _fresh(path: Path, src: Path) -> bool:
    try:
        a, b = path.stat(), src.stat()
    except OSError:
        return False
    return a.st_size == b.st_size and a.st_mtime_ns == b.st_mtime_ns


def _copy_atomic(src: Path, dst: Path) -> Path:
    """Copy next to `dst` under a temporary name (the caller renames it into place)."""
    tmp = dst.with_name(f".{dst.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    shutil.copy2(src, tmp)
    return tmp


def named(python: str | os.PathLike, key: str) -> Path:
    """The PAS-<Name>.exe that runs as `python` (a venv's Scripts\\python.exe or pythonw.exe), or `python` itself when
    no copy can be made: not Windows, turned off, not a venv, or a file that cannot be written."""
    python = Path(python)
    if not enabled():
        return python
    venv = python.parent.parent
    home, version = _venv_home(venv)
    if not home or python.parent.name.lower() != "scripts":
        return python
    windowless = python.name.lower().startswith("pythonw")
    base = home / ("pythonw.exe" if windowless else "python.exe")
    if not base.exists():
        return python
    folder = venv / FOLDER
    dest = folder / f"{NAMES[key]}.exe"
    try:
        with _lock:
            folder.mkdir(exist_ok=True)
            # The DLLs the interpreter loads at start (python3XX.dll, python3.dll, vcruntime140*.dll) sit next to it.
            for dll in home.glob("*.dll"):
                target = folder / dll.name
                if not _fresh(target, dll):
                    os.replace(_copy_atomic(dll, target), target)
            brand = branding_allowed(folder)
            stamp_file = folder / f"{dest.stem}.stamp"
            want = _stamp(base, brand)
            have = stamp_file.read_text(encoding="utf-8").strip() if stamp_file.exists() else ""
            if have != want or not dest.exists():
                tmp = _copy_atomic(base, dest)
                try:
                    if brand:
                        brand_exe(tmp, NAMES[key], version or "")
                    os.replace(tmp, dest)
                finally:
                    tmp.unlink(missing_ok=True)
                stamp_file.write_text(want + "\n", encoding="utf-8")
        return dest
    except OSError as e:  # a copy in use by a running service, a read-only folder, a full disk
        if str(dest) not in _warned:
            _warned.add(str(dest))
            warn(f"{NAMES[key]}: could not prepare {dest} ({e}); running {python.name} instead")
        return python


def named_cmd(cmd: list[str], key: str) -> list[str]:
    """`cmd` with its interpreter swapped for the PAS-<Name>.exe copy (unchanged when there is none)."""
    if not cmd:
        return cmd
    exe = named(cmd[0], key)
    return [str(exe), *cmd[1:]] if str(exe) != cmd[0] else cmd


def mark_blocked(exe: str | os.PathLike) -> None:
    """A PAS copy was refused (WinError 4551): stop branding in its folder and rebuild it as a signed copy next time."""
    exe = Path(exe)
    if not is_named(exe):
        return
    try:
        (exe.parent / BLOCKED).write_text("Windows refused a branded copy here; copies stay signed.\n", encoding="utf-8")
        (exe.parent / f"{exe.stem}.stamp").unlink(missing_ok=True)
    except OSError:
        pass


def icon_file() -> Path | None:
    """The stack's icon as an .ico on disk (for shortcuts), written on first use; None without Pillow."""
    try:
        from . import icon

        data = icon.ico_bytes()
    except ImportError:
        return None
    try:
        if not ICON_FILE.exists() or ICON_FILE.read_bytes() != data:
            ICON_FILE.parent.mkdir(parents=True, exist_ok=True)
            ICON_FILE.write_bytes(data)
        return ICON_FILE
    except OSError:
        return None


def set_app_id(key: str) -> None:
    """Give this process its own taskbar identity, so its windows group under the window icon, not Python's."""
    if IS_WINDOWS:
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"personal-agent-stack.{NAMES[key]}")
        except (OSError, AttributeError):
            pass


# ---------------------------------------------------------------- branding: icon and version resources (Windows)

RT_ICON, RT_GROUP_ICON, RT_VERSION = 3, 14, 16
LANG_EN_US = 0x0409


def strip_signature(path: Path) -> None:
    """Remove the Authenticode signature (the PE security directory and the certificate table at the file's end).
    A resource update would leave a signature that no longer matches; without one the file is plainly unsigned."""
    with open(path, "r+b") as f:
        head = f.read(4096)
        pe = struct.unpack_from("<I", head, 0x3C)[0]
        if head[pe:pe + 4] != b"PE\0\0":
            raise OSError(f"{path} is not a PE file")
        opt = pe + 24
        magic = struct.unpack_from("<H", head, opt)[0]
        dirs = opt + (112 if magic == 0x20B else 96)
        sec = dirs + 4 * 8  # IMAGE_DIRECTORY_ENTRY_SECURITY
        offset, size = struct.unpack_from("<II", head, sec)
        if not offset:
            return
        f.seek(sec)
        f.write(struct.pack("<II", 0, 0))
        f.seek(0, os.SEEK_END)
        if offset + size >= f.tell() - 8:  # the table is the file's tail (always, for signed images)
            f.truncate(offset)


def _node(key: str, value: bytes = b"", wtype: int = 1, value_len: int | None = None, children: list[bytes] = ()) -> bytes:
    """One VS_VERSIONINFO-style block: wLength, wValueLength, wType, key, padding, value, padded children."""
    body = bytearray((key + "\0").encode("utf-16-le"))
    while (6 + len(body)) % 4:
        body += b"\0"
    body += value
    for child in children:
        while (6 + len(body)) % 4:
            body += b"\0"
        body += child
    return struct.pack("<HHH", 6 + len(body), len(value) if value_len is None else value_len, wtype) + bytes(body)


def version_resource(name: str, python_version: str) -> bytes:
    """RT_VERSION data whose FileDescription (what Task Manager's Processes tab shows) is the PAS name."""
    parts = [int(p) for p in (python_version.split(".") + ["0"] * 4)[:4] if p.isdigit()] if python_version else []
    parts = (parts + [0, 0, 0, 0])[:4]
    ms, ls = (parts[0] << 16) | parts[1], (parts[2] << 16) | parts[3]
    fixed = struct.pack("<13I", 0xFEEF04BD, 0x00010000, ms, ls, ms, ls, 0x3F, 0, 0x00040004, 1, 0, 0, 0)
    strings = {
        "FileDescription": name,
        "ProductName": "personal-agent-stack",
        "InternalName": name,
        "OriginalFilename": f"{name}.exe",
        "FileVersion": python_version or "0",
        "ProductVersion": python_version or "0",
        "Comments": f"Python {python_version} interpreter, renamed for the agent stack",
    }
    entries = [_node(k, (v + "\0").encode("utf-16-le"), 1, len(v) + 1) for k, v in strings.items()]
    table = _node("040904B0", children=entries)
    sfi = _node("StringFileInfo", children=[table])
    vfi = _node("VarFileInfo", children=[_node("Translation", struct.pack("<HH", LANG_EN_US, 1200), 0)])
    return _node("VS_VERSION_INFO", fixed, 0, children=[sfi, vfi])


def icon_resources(ico: bytes, first_id: int = 1) -> tuple[list[tuple[int, bytes]], bytes]:
    """([(RT_ICON id, image)], RT_GROUP_ICON data) from an .ico file."""
    _, kind, count = struct.unpack_from("<HHH", ico, 0)
    if kind != 1:
        raise ValueError("not an icon file")
    images, group = [], bytearray(struct.pack("<HHH", 0, 1, count))
    for i in range(count):
        w, h, colors, _, planes, bits, size, offset = struct.unpack_from("<BBBBHHII", ico, 6 + 16 * i)
        rid = first_id + i
        images.append((rid, ico[offset:offset + size]))
        group += struct.pack("<BBBBHHIH", w, h, colors, 0, planes or 1, bits or 32, size, rid)
    return images, bytes(group)


def _resources(path: Path, kinds: tuple[int, ...]) -> list[tuple[int, int | str, int]]:
    """(type, name, language) of every resource of the given types in an executable."""
    from ctypes import wintypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.LoadLibraryExW.restype = wintypes.HMODULE
    k32.LoadLibraryExW.argtypes = (wintypes.LPCWSTR, wintypes.HANDLE, wintypes.DWORD)
    k32.FreeLibrary.argtypes = (wintypes.HMODULE,)
    names_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMODULE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
    langs_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMODULE, ctypes.c_void_p, ctypes.c_void_p, wintypes.WORD, ctypes.c_void_p)
    k32.EnumResourceNamesW.argtypes = (wintypes.HMODULE, ctypes.c_void_p, names_proc, ctypes.c_void_p)
    k32.EnumResourceLanguagesW.argtypes = (wintypes.HMODULE, ctypes.c_void_p, ctypes.c_void_p, langs_proc, ctypes.c_void_p)
    module = k32.LoadLibraryExW(str(path), None, 0x00000002 | 0x00000020)  # AS_DATAFILE | AS_IMAGE_RESOURCE
    if not module:
        raise ctypes.WinError(ctypes.get_last_error())
    found: list[tuple[int, int | str, int]] = []
    try:
        for kind in kinds:
            names: list[int | str] = []

            def on_name(_m, _t, name, _p):
                names.append(name if name >> 16 == 0 else ctypes.wstring_at(name))
                return True

            k32.EnumResourceNamesW(module, kind, names_proc(on_name), None)  # False when the type is absent
            for name in names:
                def on_lang(_m, _t, _n, lang, _p, name=name):
                    found.append((kind, name, lang))
                    return True

                ref = ctypes.c_wchar_p(name) if isinstance(name, str) else name
                k32.EnumResourceLanguagesW(module, kind, ref, langs_proc(on_lang), None)
    finally:
        k32.FreeLibrary(module)
    return found


def brand_exe(path: Path, name: str, python_version: str, ico: bytes | None = None) -> None:
    """Write the stack's icon and a version resource naming `name` into an executable (its signature is removed)."""
    from ctypes import wintypes

    from . import icon

    ico = ico or icon.ico_bytes()
    images, group = icon_resources(ico)
    old = _resources(path, (RT_ICON, RT_GROUP_ICON, RT_VERSION))
    strip_signature(path)
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.BeginUpdateResourceW.restype = wintypes.HANDLE
    k32.BeginUpdateResourceW.argtypes = (wintypes.LPCWSTR, wintypes.BOOL)
    k32.UpdateResourceW.argtypes = (wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, wintypes.WORD, ctypes.c_void_p, wintypes.DWORD)
    k32.EndUpdateResourceW.argtypes = (wintypes.HANDLE, wintypes.BOOL)
    handle = k32.BeginUpdateResourceW(str(path), False)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    keep: list[object] = []  # buffers must outlive EndUpdateResource

    def update(kind: int, res: int | str, lang: int, data: bytes | None) -> None:
        ref = ctypes.c_wchar_p(res) if isinstance(res, str) else res
        buf = ctypes.create_string_buffer(data, len(data)) if data else None
        keep.extend((ref, buf))
        if not k32.UpdateResourceW(handle, kind, ref, lang, buf, len(data) if data else 0):
            raise ctypes.WinError(ctypes.get_last_error())

    try:
        for kind, res, lang in old:  # drop Python's icons and version block
            update(kind, res, lang, None)
        for rid, data in images:
            update(RT_ICON, rid, 0, data)
        update(RT_GROUP_ICON, 1, 0, group)
        update(RT_VERSION, 1, LANG_EN_US, version_resource(name, python_version))
    except OSError:
        k32.EndUpdateResourceW(handle, True)
        raise
    if not k32.EndUpdateResourceW(handle, False):
        raise ctypes.WinError(ctypes.get_last_error())
