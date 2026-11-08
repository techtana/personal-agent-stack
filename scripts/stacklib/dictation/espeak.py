"""espeak-ng through ctypes: text to IPA phonemes, Kokoro's input. The library and its data come with the
espeakng-loader wheel (espeak-ng 1.52, GPL-3.0, loaded as its own DLL; it loaded under Smart App Control on the
reference machine, 2026-11-08). phonemizer and kokoro-onnx call the same three functions; calling them here avoids
their long dependency chain.

espeak-ng keeps global state, so every call holds one lock. It reads one clause at a time and drops punctuation:
speak.split_punctuation() sends only the words here and puts the punctuation back between them.
"""
from __future__ import annotations

import ctypes
import os
import threading

AUDIO_OUTPUT_SYNCHRONOUS = 0x02
DONT_EXIT = 0x8000          # espeakINITIALIZE_DONT_EXIT: without it a missing data folder ends the whole process
CHARS_UTF8 = 1
PHONEMES_IPA = 0x02
_LOCK = threading.Lock()


class EspeakError(RuntimeError):
    pass


class _Voice(ctypes.Structure):
    _fields_ = [("name", ctypes.c_char_p), ("languages", ctypes.c_char_p), ("identifier", ctypes.c_char_p),
                ("gender", ctypes.c_ubyte), ("age", ctypes.c_ubyte), ("variant", ctypes.c_ubyte),
                ("xx1", ctypes.c_ubyte), ("score", ctypes.c_int), ("spare", ctypes.c_void_p)]


def _path_bytes(path: str) -> bytes:
    """espeak-ng opens files with the C library's narrow fopen, which takes the ANSI code page on Windows."""
    return path.encode("mbcs" if os.name == "nt" else "utf-8")


class Espeak:
    def __init__(self, library: str = "", data: str = "") -> None:
        if not library:
            try:
                import espeakng_loader
            except ImportError as e:
                raise EspeakError("espeak-ng is not installed (espeakng-loader); run `stack.py dictate install`") from e
            library, data = espeakng_loader.get_library_path(), espeakng_loader.get_data_path()
        try:
            self.lib = ctypes.cdll.LoadLibrary(library)
        except OSError as e:
            hint = (" Smart App Control refused it (see CodeIntegrity event 3033)"
                    if getattr(e, "winerror", None) == 4551 else "")
            raise EspeakError(f"espeak-ng did not load: {e}.{hint}") from e
        lib = self.lib
        lib.espeak_Initialize.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_int)
        lib.espeak_Initialize.restype = ctypes.c_int
        lib.espeak_SetVoiceByProperties.argtypes = (ctypes.POINTER(_Voice),)
        lib.espeak_SetVoiceByProperties.restype = ctypes.c_int
        lib.espeak_TextToPhonemes.argtypes = (ctypes.POINTER(ctypes.c_char_p), ctypes.c_int, ctypes.c_int)
        lib.espeak_TextToPhonemes.restype = ctypes.c_char_p
        lib.espeak_Info.argtypes = (ctypes.POINTER(ctypes.c_char_p),)
        lib.espeak_Info.restype = ctypes.c_char_p
        with _LOCK:
            if lib.espeak_Initialize(AUDIO_OUTPUT_SYNCHRONOUS, 0, _path_bytes(data) if data else None, DONT_EXIT) <= 0:
                raise EspeakError("espeak-ng could not find its data folder")
        self.version = (lib.espeak_Info(None) or b"").decode("ascii", "replace")
        self.language = ""

    def _use(self, language: str) -> None:
        if language == self.language:
            return
        voice = _Voice(None, language.encode("ascii"), None, 0, 0, 0, 0, 0, None)
        if self.lib.espeak_SetVoiceByProperties(ctypes.byref(voice)) != 0:
            raise EspeakError(f"espeak-ng has no voice for {language!r}")
        self.language = language

    def phonemes(self, text: str, language: str) -> str:
        """IPA for `text` (no punctuation in it), clause after clause joined by spaces."""
        if not text.strip():
            return ""
        out: list[str] = []
        with _LOCK:
            self._use(language)
            ptr = ctypes.pointer(ctypes.c_char_p(text.encode("utf-8")))
            while ptr.contents.value:
                ps = self.lib.espeak_TextToPhonemes(ptr, CHARS_UTF8, PHONEMES_IPA)
                if ps:
                    out.append(ps.decode("utf-8", "replace").strip())
        return " ".join(p for p in out if p)
