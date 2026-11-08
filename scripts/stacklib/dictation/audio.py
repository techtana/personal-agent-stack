"""Microphone capture: 16 kHz, mono, 16-bit PCM, delivered as bytes from a background thread.

On Windows this talks to winmm.dll through ctypes. WinMM ships with Windows (signed by Microsoft), so there is no
compiled Python package for Smart App Control to refuse, unlike sounddevice or PyAudio, whose PortAudio DLLs are
unsigned. The WAVE_MAPPER device resamples whatever the microphone delivers to 16 kHz mono. Elsewhere the recorder
falls back to sounddevice when it is installed.
"""
from __future__ import annotations

import ctypes
import os
import threading
import time
from typing import Callable

RATE = 16000
SAMPLE_BYTES = 2
BLOCK = 512                 # samples per buffer: one 32 ms VAD frame
BUFFERS = 32                # about one second of queue
TEST_WAV_ENV = "AGENT_STACK_DICTATION_TEST_WAV"   # tests only: replay this file instead of opening the microphone


class RecorderError(RuntimeError):
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

    class WAVEINCAPSW(ctypes.Structure):
        _fields_ = [("wMid", wintypes.WORD), ("wPid", wintypes.WORD), ("vDriverVersion", wintypes.UINT),
                    ("szPname", wintypes.WCHAR * 32), ("dwFormats", wintypes.DWORD), ("wChannels", wintypes.WORD),
                    ("wReserved1", wintypes.WORD)]

    HWAVEIN = wintypes.HANDLE
    WAVE_MAPPER = 0xFFFFFFFF
    CALLBACK_EVENT = 0x00050000
    WHDR_DONE = 0x00000001
    _winmm.waveInOpen.argtypes = (ctypes.POINTER(HWAVEIN), wintypes.UINT, ctypes.POINTER(WAVEFORMATEX), ctypes.c_size_t,
                                  ctypes.c_size_t, wintypes.DWORD)
    _winmm.waveInOpen.restype = wintypes.UINT
    for _name in ("waveInPrepareHeader", "waveInUnprepareHeader", "waveInAddBuffer"):
        getattr(_winmm, _name).argtypes = (HWAVEIN, ctypes.POINTER(WAVEHDR), wintypes.UINT)
        getattr(_winmm, _name).restype = wintypes.UINT
    for _name in ("waveInStart", "waveInStop", "waveInReset", "waveInClose"):
        getattr(_winmm, _name).argtypes = (HWAVEIN,)
        getattr(_winmm, _name).restype = wintypes.UINT
    _winmm.waveInGetNumDevs.restype = wintypes.UINT
    _winmm.waveInGetDevCapsW.argtypes = (ctypes.c_size_t, ctypes.POINTER(WAVEINCAPSW), wintypes.UINT)
    _winmm.waveInGetDevCapsW.restype = wintypes.UINT
    _winmm.waveInGetErrorTextW.argtypes = (wintypes.UINT, wintypes.LPWSTR, wintypes.UINT)
    _k32.CreateEventW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR)
    _k32.CreateEventW.restype = wintypes.HANDLE
    _k32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    _k32.CloseHandle.argtypes = (wintypes.HANDLE,)

    def _err(code: int) -> str:
        buf = ctypes.create_unicode_buffer(256)
        _winmm.waveInGetErrorTextW(code, buf, 256)
        return buf.value or f"MMRESULT {code}"


def devices() -> list[str]:
    """Names of the input devices (WinMM cuts them to 31 characters)."""
    if os.name != "nt":
        try:
            import sounddevice as sd  # type: ignore

            return [d["name"] for d in sd.query_devices() if d.get("max_input_channels", 0) > 0]
        except Exception:  # noqa: BLE001 - optional on other systems
            return []
    names = []
    for i in range(_winmm.waveInGetNumDevs()):
        caps = WAVEINCAPSW()
        if _winmm.waveInGetDevCapsW(i, ctypes.byref(caps), ctypes.sizeof(caps)) == 0:
            names.append(caps.szPname)
    return names


def device_id(name: str) -> int | None:
    """Index of the first input device whose name contains `name` (case-insensitive); None for the Windows default."""
    if not name:
        return None
    for i, dev in enumerate(devices()):
        if name.lower() in dev.lower():
            return i
    raise RecorderError(f"no microphone matches {name!r}; found: {', '.join(devices()) or 'none'}")


class Recorder:
    """start() opens the microphone and calls on_audio(bytes) about every 32 ms from its own thread; stop() closes it."""

    def __init__(self, on_audio: Callable[[bytes], None], mic: str = "") -> None:
        self.on_audio = on_audio
        self.mic = mic
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._opened = threading.Event()
        self._error: Exception | None = None
        self._sd_stream = None

    def start(self) -> None:
        if os.environ.get(TEST_WAV_ENV):
            self._stop.clear()
            self._thread = threading.Thread(target=self._replay, args=(os.environ[TEST_WAV_ENV],), daemon=True)
            self._thread.start()
            return
        if os.name != "nt":
            self._start_sounddevice()
            return
        self._stop.clear()
        self._opened.clear()
        self._error = None
        self._thread = threading.Thread(target=self._run_winmm, name="dictation-mic", daemon=True)
        self._thread.start()
        self._opened.wait(5)
        if self._error:
            raise self._error

    def stop(self) -> None:
        if self._sd_stream is not None:
            self._sd_stream.stop()
            self._sd_stream.close()
            self._sd_stream = None
            return
        self._stop.set()
        if self._thread:
            self._thread.join(3)
            self._thread = None

    def _run_winmm(self) -> None:
        fmt = WAVEFORMATEX(1, 1, RATE, RATE * SAMPLE_BYTES, SAMPLE_BYTES, 16, 0)
        handle = HWAVEIN()
        event = _k32.CreateEventW(None, False, False, None)
        try:
            dev = device_id(self.mic)
        except RecorderError as e:
            self._error = e
            self._opened.set()
            return
        code = _winmm.waveInOpen(ctypes.byref(handle), WAVE_MAPPER if dev is None else dev, ctypes.byref(fmt),
                                 event, 0, CALLBACK_EVENT)
        if code:
            self._error = RecorderError(f"could not open the microphone: {_err(code)}")
            _k32.CloseHandle(event)
            self._opened.set()
            return
        size = BLOCK * SAMPLE_BYTES
        buffers = [ctypes.create_string_buffer(size) for _ in range(BUFFERS)]
        headers = [WAVEHDR() for _ in range(BUFFERS)]
        try:
            for buf, hdr in zip(buffers, headers):
                hdr.lpData = ctypes.cast(buf, ctypes.c_void_p)
                hdr.dwBufferLength = size
                _winmm.waveInPrepareHeader(handle, ctypes.byref(hdr), ctypes.sizeof(hdr))
                _winmm.waveInAddBuffer(handle, ctypes.byref(hdr), ctypes.sizeof(hdr))
            code = _winmm.waveInStart(handle)
            if code:
                self._error = RecorderError(f"could not start the microphone: {_err(code)}")
                return
            self._opened.set()
            nxt = 0
            while not self._stop.is_set():
                _k32.WaitForSingleObject(event, 100)
                while headers[nxt].dwFlags & WHDR_DONE and not self._stop.is_set():
                    hdr = headers[nxt]
                    if hdr.dwBytesRecorded:
                        try:
                            self.on_audio(ctypes.string_at(hdr.lpData, hdr.dwBytesRecorded))
                        except Exception as e:  # noqa: BLE001 - a consumer bug must not stop the device thread
                            print(f"[dictation] audio consumer failed: {e}", flush=True)
                    hdr.dwFlags &= ~WHDR_DONE
                    hdr.dwBytesRecorded = 0
                    _winmm.waveInAddBuffer(handle, ctypes.byref(hdr), ctypes.sizeof(hdr))
                    nxt = (nxt + 1) % BUFFERS
        finally:
            self._opened.set()
            _winmm.waveInReset(handle)
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline and not all(h.dwFlags & WHDR_DONE for h in headers):
                time.sleep(0.01)
            for hdr in headers:
                _winmm.waveInUnprepareHeader(handle, ctypes.byref(hdr), ctypes.sizeof(hdr))
            _winmm.waveInClose(handle)
            _k32.CloseHandle(event)

    def _replay(self, path: str) -> None:
        """Test hook: play a 16 kHz mono 16-bit WAV in real time instead of the microphone, then silence, so the whole
        app (VAD, Whisper, cleanup, typing) can be tested end to end without anyone speaking."""
        import wave

        with wave.open(path, "rb") as w:
            data = w.readframes(w.getnframes())
        step = BLOCK * SAMPLE_BYTES
        t0 = time.monotonic()
        n = 0
        while not self._stop.is_set():
            chunk = data[n * step:(n + 1) * step] if n * step < len(data) else bytes(step)
            self.on_audio(chunk.ljust(step, b"\0"))
            n += 1
            time.sleep(max(0.0, t0 + n * BLOCK / RATE - time.monotonic()))

    def _start_sounddevice(self) -> None:
        try:
            import sounddevice as sd  # type: ignore
        except ImportError as e:
            raise RecorderError("microphone capture on this system needs the sounddevice package") from e
        dev = None
        if self.mic:
            dev = next((i for i, d in enumerate(sd.query_devices()) if self.mic.lower() in d["name"].lower()), None)
        self._sd_stream = sd.RawInputStream(samplerate=RATE, channels=1, dtype="int16", blocksize=BLOCK, device=dev,
                                            callback=lambda data, frames, t, status: self.on_audio(bytes(data)))
        self._sd_stream.start()
