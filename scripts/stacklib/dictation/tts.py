"""The voices behind read aloud: Kokoro-82M through ONNX Runtime on the CPU, and Windows' own voices through SAPI.
Runs in the voice typing app's environment (numpy, onnxruntime, espeakng-loader, comtypes); speak.py holds the parts
the project's tests cover without it.

Measured on the reference machine (Ryzen 5 5500, 6 of 12 threads, 2026-11-08): Kokoro loads in 1.2 s and speaks at
about three times real time on the CPU, the same for the fp32 weights (326 MB) and the int8 ones (92 MB): a short
sentence is ready in 0.8 s, 17 s of speech in 6 s. Whisper transcribed its output back word for word. A Windows voice
makes 6 s of speech in 0.02-0.05 s. Neither touches the GPU.

Every reading is one usage record (source read-aloud, kind speech) for the tray's Usage tab: seconds of speech, the
time the voice worked, phoneme tokens, the voice; never the text.
"""
from __future__ import annotations

import gc
import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .. import usage_log
from . import speak
from .speak import SAMPLE_RATE, Voice

CLIENT = "Read aloud"


class SpeechError(RuntimeError):
    """Why a voice could not speak; the reader shows it in the bubble."""


@dataclass
class Audio:
    pcm: bytes            # 16-bit mono at SAMPLE_RATE
    seconds: float
    tokens: int = 0       # phoneme tokens Kokoro read
    run_s: float = 0.0    # time the voice worked
    load_s: float = 0.0   # time spent loading the model for this piece


def _short(e: BaseException) -> str:
    text = str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__
    return text[:160]


def _pcm16(audio: np.ndarray) -> bytes:
    return (np.clip(audio, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()


# ---------------------------------------------------------------- Kokoro

def kokoro_file(name: str, download: bool = True) -> Path:
    """A file of the pinned Kokoro repository from the Hugging Face cache; downloaded only when it is not there yet
    (huggingface_hub would otherwise ask huggingface.co for the newest revision every time)."""
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    from huggingface_hub import hf_hub_download

    try:
        return Path(hf_hub_download(speak.KOKORO_REPO, name, revision=speak.KOKORO_REVISION, local_files_only=True))
    except Exception:  # noqa: BLE001 - LocalEntryNotFoundError and friends: not cached yet
        if not download:
            raise
    return Path(hf_hub_download(speak.KOKORO_REPO, name, revision=speak.KOKORO_REVISION))


def kokoro_cached(variant: str, voices: tuple[str, ...] = ("af_heart",)) -> bool:
    try:
        for name in (speak.KOKORO_FILES[variant], "tokenizer.json", *(f"voices/{v}.bin" for v in voices)):
            kokoro_file(name, download=False)
        return True
    except Exception:  # noqa: BLE001
        return False


class Kokoro:
    """Kokoro-82M: loads on first use, is freed after read_aloud.unload_after_min idle minutes."""

    def __init__(self, log=print) -> None:
        self.log = log
        self.lock = threading.RLock()          # one synthesis at a time; also guards load and unload
        self.session = None
        self.espeak = None
        self.vocab: dict[str, int] = {}
        self.styles: dict[str, np.ndarray] = {}
        self.variant = ""
        self.state = "unloaded"                # unloaded | loading | ready | failed
        self.note = ""
        self.load_seconds = 0.0
        self.last_used = time.monotonic()

    def ready(self, variant: str) -> bool:
        return self.state == "ready" and self.variant == variant

    def load(self, variant: str) -> float:
        """Load (or switch to) the weights; returns the seconds it took, 0 when they were loaded already."""
        with self.lock:
            if self.ready(variant):
                return 0.0
            self.unload(quiet=True)
            self.state = "loading"
            t0 = time.monotonic()
            try:
                import onnxruntime as ort

                from .espeak import Espeak

                self.espeak = Espeak()
                tokenizer = json.loads(kokoro_file("tokenizer.json", download=False).read_text(encoding="utf-8"))
                self.vocab = dict(tokenizer["model"]["vocab"])
                so = ort.SessionOptions()
                so.intra_op_num_threads = max(1, (os.cpu_count() or 4) // 2)
                so.inter_op_num_threads = 1
                so.add_session_config_entry("session.intra_op.allow_spinning", "0")  # idle threads sleep
                self.session = ort.InferenceSession(str(kokoro_file(speak.KOKORO_FILES[variant], download=False)), so,
                                                    providers=["CPUExecutionProvider"])
            except Exception as e:  # noqa: BLE001 - shown in the bubble; Windows voices still work
                self.state, self.note = "failed", f"Kokoro could not load: {_short(e)}"
                self.session = self.espeak = None
                self.log(f"[read] {self.note}")
                raise SpeechError(self.note) from e
            self.variant, self.state, self.note = variant, "ready", ""
            self.load_seconds = time.monotonic() - t0
            self.last_used = time.monotonic()
            self.log(f"[read] Kokoro ({variant}) ready on the CPU in {self.load_seconds:.1f} s, "
                     f"espeak-ng {self.espeak.version}")
            return self.load_seconds

    def unload(self, quiet: bool = False) -> None:
        with self.lock:
            if self.session is None:
                return
            self.session = None
            self.styles.clear()
            self.state = "unloaded"
        gc.collect()
        if not quiet:
            self.log("[read] Kokoro unloaded (idle); the next reading loads it again")

    def unload_if_idle(self, minutes: float) -> None:
        if minutes and self.state == "ready" and time.monotonic() - self.last_used > minutes * 60:
            self.unload()

    def _style(self, voice_id: str) -> np.ndarray:
        table = self.styles.get(voice_id)
        if table is None:
            table = np.fromfile(kokoro_file(f"voices/{voice_id}.bin"), dtype=np.float32).reshape(-1, 1, 256)
            self.styles[voice_id] = table
        return table

    def phonemes(self, text: str, language: str) -> str:
        parts = [piece if punct else self.espeak.phonemes(piece, language)
                 for punct, piece in speak.split_punctuation(speak.for_phonemes(text, language))]
        return speak.tidy_phonemes("".join(parts), language)

    def synth(self, text: str, voice: Voice, speed: float, variant: str) -> Audio:
        load_s = self.load(variant)
        with self.lock:
            if self.session is None:
                raise SpeechError("Kokoro was unloaded")
            t0 = time.monotonic()
            self.last_used = t0
            table = self._style(voice.id)
            ps = self.phonemes(text, voice.language)
            chunks, tokens = [], 0
            for ids in speak.split_ids(ps, self.vocab):
                style = table[min(len(ids), len(table) - 1)]
                wav = self.session.run(None, {"input_ids": np.array([[0, *ids, 0]], dtype=np.int64),
                                              "style": style.astype(np.float32),
                                              "speed": np.array([speed], dtype=np.float32)})[0]
                chunks.append(np.asarray(wav, dtype=np.float32).reshape(-1))
                tokens += len(ids)
            self.last_used = time.monotonic()
            run_s = self.last_used - t0
        audio = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
        return Audio(_pcm16(audio), len(audio) / SAMPLE_RATE, tokens, run_s, load_s)


# ---------------------------------------------------------------- Windows voices

class WindowsVoices:
    """SAPI through comtypes (pure Python): each call makes its own voice object on the calling thread, into a memory
    stream at Kokoro's format, so both kinds of voice play the same way. OneCore voices work through SAPI when their
    token is opened from the Speech_OneCore registry path."""

    SVSF_IS_NOT_XML = 16      # read "<" as text, never as SSML markup
    SAFT_24KHZ_16BIT_MONO = 26

    def __init__(self) -> None:
        self.local = threading.local()

    def _com(self):
        import comtypes
        from comtypes.client import CreateObject

        if not getattr(self.local, "ready", False):
            comtypes.CoInitialize()
            self.local.ready = True
        return CreateObject

    def synth(self, text: str, voice: Voice, speed: float) -> Audio:
        t0 = time.monotonic()
        try:
            create = self._com()
            sp = create("SAPI.SpVoice", dynamic=True)
            if voice.token:
                token = create("SAPI.SpObjectToken", dynamic=True)
                token.SetId(voice.token, "", False)
                sp.Voice = token
            sp.Rate = speak.sapi_rate(speed)
            stream = create("SAPI.SpMemoryStream", dynamic=True)
            fmt = stream.Format
            fmt.Type = self.SAFT_24KHZ_16BIT_MONO
            stream.Format = fmt
            sp.AudioOutputStream = stream
            sp.Speak(text, self.SVSF_IS_NOT_XML)
            pcm = bytes(stream.GetData())
        except Exception as e:  # noqa: BLE001 - COM errors carry HRESULTs, not sentences
            raise SpeechError(f"the Windows voice {voice.name} failed: {_short(e)}") from e
        return Audio(pcm, len(pcm) / 2 / SAMPLE_RATE, 0, time.monotonic() - t0, 0.0)


# ---------------------------------------------------------------- both

class Speech:
    """What the reader calls: the voices available now, one piece of speech, and the usage record of a reading."""

    def __init__(self, log=print) -> None:
        self.log = log
        self.kokoro = Kokoro(log)
        self.windows = WindowsVoices()
        self._win_voices: tuple[float, list[Voice]] = (-1e9, [])
        self._cached: dict[str, tuple[float, bool]] = {}   # Kokoro variant -> (checked at, files on disk)
        self._modules: dict[str, bool] = {}

    def _has(self, module: str) -> bool:
        """A package of read aloud is in this environment (the installer's Read aloud feature adds them)."""
        if module not in self._modules:
            import importlib.util

            self._modules[module] = importlib.util.find_spec(module) is not None
        return self._modules[module]

    def kokoro_installed(self) -> bool:
        """espeak-ng and ONNX Runtime are in this environment (the weights may still be missing)."""
        return self._has("espeakng_loader") and self._has("onnxruntime")

    def kokoro_downloaded(self, variant: str) -> bool:
        """Kokoro's files are in the Hugging Face cache; checked once a minute. Reading never downloads them: a
        surprise 0.35 GB download is not a reading; the installer fetches them."""
        at, ok = self._cached.get(variant, (-1e9, False))
        if time.monotonic() - at > 60:
            ok = kokoro_cached(variant)
            self._cached[variant] = (time.monotonic(), ok)
        return ok

    def missing(self, cfg: speak.Config) -> str:
        """Why read aloud has fewer voices than it should, or "" when nothing is missing."""
        windows = self._has("comtypes")
        if not self.kokoro_installed() and not windows:
            return ("Read aloud is not installed. Tick Read aloud in the installer (tray: Add features...), or run "
                    "`uv run scripts/stack.py read-aloud install`.")
        if cfg.kokoro == "off":
            return ""
        if not self.kokoro_installed():
            return "Kokoro is not installed (espeak-ng is missing); run `uv run scripts/stack.py read-aloud install`."
        if self.kokoro.state == "failed":
            return self.kokoro.note
        if not self.kokoro_downloaded(cfg.kokoro):
            return (f"Kokoro's {cfg.kokoro} weights are not downloaded yet; run `uv run scripts/stack.py read-aloud "
                    "install`.")
        return ""

    def voices(self, cfg: speak.Config) -> list[Voice]:
        """Kokoro's voices (when installed, downloaded and not turned off or broken), then this PC's Windows voices
        (re-read from the registry once a minute, so a newly added voice shows up; they need comtypes)."""
        out: list[Voice] = []
        kokoro = cfg.kokoro != "off" and self.kokoro_installed() and self.kokoro.state != "failed"
        if kokoro and self.kokoro_downloaded(cfg.kokoro):
            out += speak.kokoro_voices()
        if not self._has("comtypes"):
            return out
        at, cached = self._win_voices
        if time.monotonic() - at > 60:
            try:
                cached = speak.windows_voices()
            except OSError:
                cached = []
            self._win_voices = (time.monotonic(), cached)
        return out + cached

    def ready(self, voice: Voice, cfg: speak.Config) -> bool:
        return voice.engine != "kokoro" or self.kokoro.ready(cfg.kokoro)

    def synth(self, text: str, voice: Voice, speed: float, cfg: speak.Config) -> Audio:
        if voice.engine == "kokoro":
            if cfg.kokoro == "off":
                raise SpeechError("Kokoro is off (read_aloud.kokoro)")
            return self.kokoro.synth(text, voice, speed, cfg.kokoro)
        return self.windows.synth(text, voice, speed)

    def model_name(self, voice: Voice, cfg: speak.Config) -> str:
        if voice.engine == "kokoro":
            return "kokoro-82m" + ("" if cfg.kokoro == "fp32" else f"-{cfg.kokoro}")
        return f"windows {voice.name}"

    def record(self, voice: Voice, cfg: speak.Config, *, audio_s: float, run_s: float, load_s: float, tokens: int,
               wall_s: float, stopped: bool, failed: str = "", client: str = CLIENT) -> None:
        """One usage record per reading (the tray's Usage tab); never the text."""
        try:
            usage_log.record(
                "read-aloud", self.model_name(voice, cfg), "speech", client=client,
                status="failure" if failed else "success", error=failed, latency_ms=wall_s * 1000,
                load_ms=load_s * 1000 if load_s else None, run_ms=run_s * 1000, input_tokens=tokens, audio_s=audio_s,
                detail={k: v for k, v in (("engine", voice.engine), ("voice", voice.id), ("language", voice.language),
                                          ("device", "cpu"), ("speed", cfg.speed), ("stopped", stopped)) if v})
        except Exception as e:  # noqa: BLE001 - a usage record must never break reading
            self.log(f"[read] usage record failed: {_short(e)}")

    def unload_if_idle(self, minutes: float) -> None:
        self.kokoro.unload_if_idle(minutes)

    def health(self) -> dict:
        k = self.kokoro
        return {"engine": k.state, "model": f"kokoro-82m {k.variant}".strip() if k.variant else "",
                "device": "cpu", "note": k.note, "idle_s": round(time.monotonic() - k.last_used)}


def download(profile: dict, report=lambda *a: None) -> str:
    """Fetch Kokoro's weights (read_aloud.kokoro), its tokenizer and every offered voice into the Hugging Face cache,
    so reading never waits for a download; about 0.35 GB for fp32. Called by `stack.py dictate install`."""
    cfg = speak.Config.from_profile(profile)
    if cfg.kokoro == "off":
        return "Kokoro is off (read_aloud.kokoro: off); read aloud uses Windows voices"
    names = [speak.KOKORO_FILES[cfg.kokoro], "tokenizer.json", "config.json",
             *(f"voices/{v}.bin" for v in speak.KOKORO_VOICE_IDS)]
    missing = []
    for name in names:
        try:
            kokoro_file(name, download=False)
        except Exception:  # noqa: BLE001 - not cached
            missing.append(name)
    if not missing:
        return f"Kokoro {cfg.kokoro} and its {len(speak.KOKORO_VOICE_IDS)} voices already cached"
    report(f"downloading Kokoro-82M ({cfg.kokoro}, about {speak.KOKORO_SIZES_MB[cfg.kokoro]} MB) and "
           f"{len(speak.KOKORO_VOICE_IDS)} voices into the Hugging Face cache")
    for name in missing:
        kokoro_file(name)
    return f"downloaded Kokoro {cfg.kokoro} and {len(speak.KOKORO_VOICE_IDS)} voices"
