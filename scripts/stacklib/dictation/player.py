"""Play 16-bit mono PCM through WinMM (waveOut), one piece after another, from a thread of its own: the read aloud
voice. WinMM ships with Windows (signed by Microsoft), so no compiled package is needed, as audio.py records with
waveIn. The default output device (WAVE_MAPPER) follows Windows' sound settings.

Pieces queue while earlier ones play; at most two are handed to Windows at a time, so stop() ends the sound within
about 50 ms. on_start(tag) runs on the player thread when a piece starts playing (the bubble shows that sentence).

FilePlayer has the same methods and writes a WAV file instead, in real time; the app uses it when the environment
variable AGENT_STACK_READ_TEST_OUT names a file, so end-to-end tests make no sound.
"""
from __future__ import annotations

import ctypes
import os
import threading
import time
import wave
from collections import deque
from typing import Callable

TEST_OUT_ENV = "AGENT_STACK_READ_TEST_OUT"
IN_FLIGHT = 2


class PlayerError(RuntimeError):
    pass


if os.name == "nt":
    from ctypes import wintypes

    _winmm = ctypes.WinDLL("winmm")
    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class WAVEFORMATEX(ctypes.Structure):
        _fields_ = [("wFormatTag", wintypes.WORD), ("nChannels", wintypes.WORD), ("nSamplesPerSec", wintypes.DWORD),
                    ("nAvgBytesPerSec", wintypes.DWORD), ("nBlockAlign", wintypes.WORD),
                    ("wBitsPerSample", wintypes.WORD), ("cbSize", wintypes.WORD)]

    class WAVEHDR(ctypes.Structure):
        pass

    WAVEHDR._fields_ = [("lpData", ctypes.c_void_p), ("dwBufferLength", wintypes.DWORD),
                        ("dwBytesRecorded", wintypes.DWORD), ("dwUser", ctypes.c_size_t), ("dwFlags", wintypes.DWORD),
                        ("dwLoops", wintypes.DWORD), ("lpNext", ctypes.POINTER(WAVEHDR)), ("reserved", ctypes.c_size_t)]

    HWAVEOUT = wintypes.HANDLE
    WAVE_MAPPER = 0xFFFFFFFF
    CALLBACK_EVENT = 0x00050000
    WHDR_DONE = 0x00000001
    _winmm.waveOutOpen.argtypes = (ctypes.POINTER(HWAVEOUT), wintypes.UINT, ctypes.POINTER(WAVEFORMATEX),
                                   ctypes.c_size_t, ctypes.c_size_t, wintypes.DWORD)
    _winmm.waveOutOpen.restype = wintypes.UINT
    for _name in ("waveOutPrepareHeader", "waveOutUnprepareHeader", "waveOutWrite"):
        getattr(_winmm, _name).argtypes = (HWAVEOUT, ctypes.POINTER(WAVEHDR), wintypes.UINT)
        getattr(_winmm, _name).restype = wintypes.UINT
    for _name in ("waveOutReset", "waveOutPause", "waveOutRestart", "waveOutClose"):
        getattr(_winmm, _name).argtypes = (HWAVEOUT,)
        getattr(_winmm, _name).restype = wintypes.UINT
    _winmm.waveOutGetErrorTextW.argtypes = (wintypes.UINT, wintypes.LPWSTR, wintypes.UINT)
    _k32.CreateEventW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR)
    _k32.CreateEventW.restype = wintypes.HANDLE
    _k32.SetEvent.argtypes = (wintypes.HANDLE,)
    _k32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    _k32.CloseHandle.argtypes = (wintypes.HANDLE,)

    def _err(code: int) -> str:
        buf = ctypes.create_unicode_buffer(256)
        _winmm.waveOutGetErrorTextW(code, buf, 256)
        return buf.value or f"MMRESULT {code}"


class _Base:
    """Queue, flags and timing shared by both players."""

    def __init__(self, rate: int, on_start: Callable[[object], None] | None) -> None:
        self.rate = rate
        self.on_start = on_start
        self.lock = threading.Lock()
        self.pieces: deque = deque()
        self.finished = False
        self.stopped = False
        self.paused = False
        self.queued_s = 0.0     # every piece handed to play()
        self.played_s = 0.0     # pieces that have finished playing
        self.done = threading.Event()
        self.thread: threading.Thread | None = None

    def _seconds(self, pcm: bytes) -> float:
        return len(pcm) / 2 / self.rate

    def play(self, pcm: bytes, tag: object = None) -> None:
        with self.lock:
            if self.stopped:
                return
            self.pieces.append((bytes(pcm), tag))
            self.queued_s += self._seconds(pcm)
        self._wake()

    def finish(self) -> None:
        """No more pieces: the player ends once the last one has played."""
        with self.lock:
            self.finished = True
        self._wake()

    def ahead(self) -> float:
        """Seconds queued that have not finished playing."""
        return max(0.0, self.queued_s - self.played_s)

    def wait(self, timeout: float | None = None) -> bool:
        return self.done.wait(timeout)

    def _started(self, tag: object) -> None:
        if self.on_start is not None:
            try:
                self.on_start(tag)
            except Exception as e:  # noqa: BLE001 - a UI problem must not stop the sound
                print(f"[read] on_start failed: {e}", flush=True)

    def _wake(self) -> None:
        pass


class Player(_Base):
    def __init__(self, rate: int = 24000, on_start: Callable[[object], None] | None = None) -> None:
        super().__init__(rate, on_start)
        self.handle = None
        self.event = None
        self.opened = threading.Event()
        self.error: Exception | None = None

    def start(self) -> None:
        if os.name != "nt":
            raise PlayerError("sound output is only written for Windows")
        self.thread = threading.Thread(target=self._run, name="read-aloud-player", daemon=True)
        self.thread.start()
        self.opened.wait(5)
        if self.error:
            raise self.error

    def _wake(self) -> None:
        if self.event:
            _k32.SetEvent(self.event)

    def pause(self) -> None:
        with self.lock:
            if self.handle and not self.paused and not self.stopped:
                _winmm.waveOutPause(self.handle)
                self.paused = True

    def resume(self) -> None:
        with self.lock:
            if self.handle and self.paused and not self.stopped:
                _winmm.waveOutRestart(self.handle)
                self.paused = False

    def stop(self) -> None:
        with self.lock:
            self.stopped = True
            self.pieces.clear()
        self._wake()

    def _run(self) -> None:
        fmt = WAVEFORMATEX(1, 1, self.rate, self.rate * 2, 2, 16, 0)
        handle = HWAVEOUT()
        self.event = _k32.CreateEventW(None, False, False, None)
        code = _winmm.waveOutOpen(ctypes.byref(handle), WAVE_MAPPER, ctypes.byref(fmt), self.event, 0, CALLBACK_EVENT)
        if code:
            self.error = PlayerError(f"no sound output: {_err(code)}")
            _k32.CloseHandle(self.event)
            self.event = None
            self.opened.set()
            self.done.set()
            return
        self.handle = handle
        self.opened.set()
        flight: deque = deque()   # (header, buffer, tag, seconds), in the order Windows plays them
        try:
            while True:
                with self.lock:
                    if self.stopped:
                        break
                    while len(flight) < IN_FLIGHT and self.pieces:
                        pcm, tag = self.pieces.popleft()
                        buf = ctypes.create_string_buffer(pcm, len(pcm))
                        hdr = WAVEHDR()
                        hdr.lpData = ctypes.cast(buf, ctypes.c_void_p)
                        hdr.dwBufferLength = len(pcm)
                        _winmm.waveOutPrepareHeader(handle, ctypes.byref(hdr), ctypes.sizeof(hdr))
                        _winmm.waveOutWrite(handle, ctypes.byref(hdr), ctypes.sizeof(hdr))
                        flight.append((hdr, buf, tag, self._seconds(pcm)))
                        if len(flight) == 1:
                            self._started(tag)
                    if not flight and self.finished and not self.pieces:
                        break
                _k32.WaitForSingleObject(self.event, 50)
                while flight and flight[0][0].dwFlags & WHDR_DONE:
                    hdr, _buf, _tag, secs = flight.popleft()
                    _winmm.waveOutUnprepareHeader(handle, ctypes.byref(hdr), ctypes.sizeof(hdr))
                    self.played_s += secs
                    if flight:
                        self._started(flight[0][2])
        finally:
            with self.lock:
                self.handle = None
            _winmm.waveOutReset(handle)
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline and not all(h.dwFlags & WHDR_DONE for h, *_ in flight):
                time.sleep(0.01)
            for hdr, *_ in flight:
                _winmm.waveOutUnprepareHeader(handle, ctypes.byref(hdr), ctypes.sizeof(hdr))
            _winmm.waveOutClose(handle)
            event, self.event = self.event, None
            _k32.CloseHandle(event)
            self.done.set()


class FilePlayer(_Base):
    """The same interface, writing the sound into a WAV file in real time (scaled by `pace`; 0 = as fast as it can),
    so a test can stop or pause it part of the way through."""

    def __init__(self, path: str, rate: int = 24000, on_start: Callable[[object], None] | None = None,
                 pace: float = 1.0) -> None:
        super().__init__(rate, on_start)
        self.path, self.pace = path, pace
        self.wake = threading.Event()
        self.resumed = threading.Event()
        self.resumed.set()

    def start(self) -> None:
        self.thread = threading.Thread(target=self._run, name="read-aloud-file-player", daemon=True)
        self.thread.start()

    def _wake(self) -> None:
        self.wake.set()

    def pause(self) -> None:
        self.paused = True
        self.resumed.clear()

    def resume(self) -> None:
        self.paused = False
        self.resumed.set()

    def stop(self) -> None:
        with self.lock:
            self.stopped = True
            self.pieces.clear()
        self.resumed.set()
        self.wake.set()

    def _run(self) -> None:
        try:
            with wave.open(self.path, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(self.rate)
                while True:
                    with self.lock:
                        item = self.pieces.popleft() if self.pieces else None
                        end = self.stopped or (item is None and self.finished)
                    if end:
                        break
                    if item is None:
                        self.wake.wait(0.05)
                        self.wake.clear()
                        continue
                    pcm, tag = item
                    self._started(tag)
                    step = self.rate // 20 * 2      # 50 ms of sound at a time, so stop and pause act quickly
                    for i in range(0, len(pcm), step):
                        self.resumed.wait()
                        if self.stopped:
                            break
                        w.writeframes(pcm[i:i + step])
                        if self.pace:
                            time.sleep(len(pcm[i:i + step]) / 2 / self.rate / self.pace)
                    self.played_s += self._seconds(pcm)
        finally:
            self.done.set()


def make(on_start: Callable[[object], None] | None, rate: int = 24000):
    """The player the app uses: the speakers, or the test file named by AGENT_STACK_READ_TEST_OUT."""
    out = os.environ.get(TEST_OUT_ENV, "")
    return FilePlayer(out, rate, on_start) if out else Player(rate, on_start)
