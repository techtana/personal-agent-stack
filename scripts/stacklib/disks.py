"""Drive speed check: how fast each drive reads and writes, and which drive should hold models, tools and caches.

Uses `winsat disk` when the process runs as administrator (winsat does nothing without it: no output, exit code 0)
and otherwise times a 256 MB test file: written and flushed, then read back past the OS cache. The thresholds come
from SEKAIHOME (2026-11-01): a Crucial X8 USB SSD measured 41 MB/s on a USB 2.0 link and 376 MB/s on USB 3, against
2,762 MB/s for the internal NVMe drive. docs/manuals/choosing-drives.md explains the advice in plain language.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import string
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from . import IS_WINDOWS

SLOW_MBPS = 100     # below this a drive is slower than a hard disk; a USB SSD this slow is usually on a USB 2.0 link
GOOD_MBPS = 200     # enough for models and games: a 6.6 GB model loads in about 30 s
TEST_MB = 256
CHUNK = 4 * 1024 * 1024


@dataclass
class DriveSpeed:
    root: str                       # "C:\\" or "/"
    read_mbps: float | None = None
    write_mbps: float | None = None
    random_mbps: float | None = None   # winsat only
    method: str = ""                # "winsat" or "test file"
    bus: str = ""                   # "NVMe", "SATA", "USB", ... ("" when unknown)
    free_gb: float = 0.0
    error: str = ""

    @property
    def letter(self) -> str:
        return self.root.rstrip("\\/") or self.root

    @property
    def slow(self) -> bool:
        return self.read_mbps is not None and self.read_mbps < SLOW_MBPS

    @property
    def good(self) -> bool:
        return self.read_mbps is not None and self.read_mbps >= GOOD_MBPS

    def summary(self) -> str:
        if self.error:
            return f"{self.letter} not measured ({self.error})"
        parts = [f"read {self.read_mbps:.0f} MB/s" if self.read_mbps is not None else "read ?",
                 f"write {self.write_mbps:.0f} MB/s" if self.write_mbps is not None else "write ?"]
        bus = f"{self.bus}, " if self.bus else ""
        return f"{self.letter} {', '.join(parts)} ({bus}{self.free_gb:.0f} GB free, {self.method})"


def drive_of(path: str) -> str:
    return Path(path).anchor if path else ""


def list_drives() -> list[str]:
    """Local fixed and removable drives (Windows); the root file system elsewhere."""
    if not IS_WINDOWS:
        return ["/"]
    import ctypes

    out = []
    mask = ctypes.windll.kernel32.GetLogicalDrives()
    for i, c in enumerate(string.ascii_uppercase):
        if mask >> i & 1:
            root = f"{c}:\\"
            if ctypes.windll.kernel32.GetDriveTypeW(root) in (2, 3):   # DRIVE_REMOVABLE, DRIVE_FIXED
                out.append(root)
    return out


def bus_types() -> dict[str, str]:
    """Drive letter -> bus type ("USB", "NVMe", "SATA", ...) from Get-Disk; {} when PowerShell cannot say."""
    if not IS_WINDOWS:
        return {}
    ps = ("Get-Partition | Where-Object DriveLetter | ForEach-Object { [pscustomobject]@{ l = [string]$_.DriveLetter; "
          "b = [string](Get-Disk -Number $_.DiskNumber).BusType } } | ConvertTo-Json -Compress")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=30)
        rows = json.loads(r.stdout or "[]")
    except (OSError, subprocess.SubprocessError, ValueError):
        return {}
    rows = [rows] if isinstance(rows, dict) else rows
    return {f"{x['l']}:\\": x["b"] for x in rows if x.get("l")}


def is_admin() -> bool:
    if not IS_WINDOWS:
        return hasattr(os, "geteuid") and os.geteuid() == 0
    import ctypes

    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


_WINSAT_LINE = re.compile(r"Disk\s+(Random|Sequential)\s+[\d.]+\s+(Read|Write)\s+([\d.]+)\s+MB/s")


def parse_winsat(text: str) -> dict[str, float]:
    """{"seq read": MB/s, "seq write": ..., "random read": ...} from `winsat disk` output."""
    out = {}
    for kind, op, mbps in _WINSAT_LINE.findall(text):
        out[f"{'seq' if kind == 'Sequential' else 'random'} {op.lower()}"] = float(mbps)
    return out


def winsat(root: str) -> dict[str, float]:
    if not (IS_WINDOWS and is_admin() and shutil.which("winsat")):
        return {}
    try:
        r = subprocess.run(["winsat", "disk", "-drive", root[0].lower()], capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError):
        return {}
    return parse_winsat(r.stdout)


def _test_dir(root: str) -> tuple[Path, bool]:
    """A writable folder on that drive, and whether this check created it (and must remove it)."""
    tmp = Path(tempfile.gettempdir())
    if tmp.anchor.lower() == root.lower():
        return tmp, False
    d = Path(root) / "agent-stack-speedtest"
    d.mkdir(exist_ok=True)
    return d, True


def _read_uncached(path: Path) -> float:
    """Seconds to read the whole file without the OS cache (Windows: FILE_FLAG_NO_BUFFERING)."""
    if IS_WINDOWS:
        import ctypes
        from ctypes import wintypes

        k32 = ctypes.windll.kernel32
        k32.CreateFileW.restype = wintypes.HANDLE
        k32.VirtualAlloc.restype = ctypes.c_void_p
        k32.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        k32.VirtualFree.argtypes = [ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD]
        handle = k32.CreateFileW(str(path), 0x80000000, 1, None, 3, 0x20000000 | 0x08000000, None)  # GENERIC_READ, NO_BUFFERING | SEQUENTIAL_SCAN
        if handle in (None, wintypes.HANDLE(-1).value):
            raise ctypes.WinError()
        buf = k32.VirtualAlloc(None, CHUNK, 0x3000, 0x04)   # page-aligned, as NO_BUFFERING requires
        try:
            got = wintypes.DWORD()
            start = time.perf_counter()
            while k32.ReadFile(handle, buf, CHUNK, ctypes.byref(got), None) and got.value:
                pass
            return time.perf_counter() - start
        finally:
            k32.VirtualFree(buf, 0, 0x8000)
            k32.CloseHandle(handle)
    fd = os.open(path, os.O_RDONLY)
    try:
        if hasattr(os, "posix_fadvise"):
            os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)   # drop the pages the write left in the cache
        start = time.perf_counter()
        while os.read(fd, CHUNK):
            pass
        return time.perf_counter() - start
    finally:
        os.close(fd)


def file_test(root: str, mb: int = TEST_MB) -> tuple[float, float]:
    """(read MB/s, write MB/s) for a test file written, flushed to the drive, then read back past the cache."""
    folder, created = _test_dir(root)
    path = folder / f"agent-stack-speedtest-{os.getpid()}.bin"
    block = os.urandom(CHUNK)   # random bytes: a compressing controller cannot shortcut them
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0))
        try:
            start = time.perf_counter()
            for _ in range(mb * 1024 * 1024 // CHUNK):
                os.write(fd, block)
            os.fsync(fd)
            write_s = time.perf_counter() - start
        finally:
            os.close(fd)
        read_s = _read_uncached(path)
        return mb / max(read_s, 1e-6), mb / max(write_s, 1e-6)
    finally:
        path.unlink(missing_ok=True)
        if created:
            try:
                folder.rmdir()
            except OSError:
                pass


def measure(root: str, bus: str = "") -> DriveSpeed:
    ds = DriveSpeed(root=root, bus=bus)
    try:
        ds.free_gb = shutil.disk_usage(root).free / 1e9
    except OSError as e:
        ds.error = str(e)
        return ds
    if ds.free_gb < TEST_MB / 1000 * 2:
        ds.error = "too little free space for the test file"
        return ds
    w = winsat(root)
    if w.get("seq read"):
        ds.read_mbps, ds.write_mbps, ds.random_mbps, ds.method = w.get("seq read"), w.get("seq write"), w.get("random read"), "winsat"
        return ds
    try:
        ds.read_mbps, ds.write_mbps = file_test(root)
        ds.method = "test file"
    except OSError as e:
        ds.error = e.strerror or str(e)
    return ds


def measure_all(roots: list[str] | None = None, report=None) -> list[DriveSpeed]:
    roots = [f"{r[0].upper()}:\\" if IS_WINDOWS and len(r) <= 3 and r[1:2] == ":" else r for r in roots or list_drives()]
    buses = bus_types()
    out = []
    for i, r in enumerate(roots):
        if report:
            report(f"measuring {r.rstrip(chr(92))} ({i + 1} of {len(roots)})", i / len(roots))
        out.append(measure(r, buses.get(r, "")))
    return out


def advise(speeds: list[DriveSpeed], model_store: str, tool_dir: str, models_gb: float) -> tuple[list[str], str]:
    """(warnings, suggestion). Models and caches want space and at least GOOD_MBPS; tools want the internal drive."""
    by_root = {s.root.lower(): s for s in speeds}
    warnings = []
    for s in speeds:
        if s.slow:
            hint = (" That is USB 2.0 speed: use a USB 3 port on the back of the PC and the drive's own cable, "
                    "or turn the USB-C plug over." if s.bus == "USB" or s.read_mbps < 50 else "")
            warnings.append(f"{s.letter} reads at only {s.read_mbps:.0f} MB/s, slower than a hard disk.{hint}")
    store = by_root.get(drive_of(model_store).lower())
    suggestion = ""
    if store and not store.error and not store.good:
        room = [s for s in speeds if s.good and s.free_gb >= models_gb + 20]
        best = max(room, key=lambda s: (s.bus != "USB", s.read_mbps), default=None)
        if best and best.root.lower() != store.root.lower():
            suggestion = (f"Models: {best.letter} would load them faster ({best.read_mbps:.0f} MB/s, {best.free_gb:.0f} GB free); "
                          f"run the installer again and choose a folder there, such as {best.letter}\\ollama\\models.")
        else:
            suggestion = f"Models: {store.letter} works, but every cold model load will be slow until the drive is faster."
    tools = by_root.get(drive_of(tool_dir).lower())
    if tools and tools.bus == "USB":
        warnings.append(f"The Python tools are on {tools.letter}, a USB drive. They start at login, so when the drive is "
                        "unplugged the stack does not start; keep them on the internal drive.")
    return warnings, suggestion
