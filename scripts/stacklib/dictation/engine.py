"""The speech model (dictation.model): load on the GPU when it works, else on the CPU; free its memory when idle.

Whisper runs through faster-whisper. Measured on the reference machine (RTX 3060 12 GB, qwen3.5:9b resident,
2026-11-07): large-v3-turbo int8_float16 loads in 5-8 s from the USB SSD and transcribes 3.5 s of speech in 0.3 s and 15
s in 0.6 s. On the Ryzen 5 5500 the same model with int8 needed 9.7 s for the 15 s clip, too slow to wait for, so the CPU
fallback uses `cpu_model` (default small). The other engines (stt.py) run NVIDIA Parakeet TDT on the CPU, where it makes
24x real time, and NVIDIA Canary-Qwen 2.5B on the GPU through Vulkan. A model that is slow on the CPU (more than
CPU_OK_S per 15 s of speech) gives way to `cpu_model` there, as Whisper large does.
"""
from __future__ import annotations

import gc
import os
import threading
import time

import numpy as np

from .. import usage_log
from . import Config, stt
from . import gpu as _gpu
from .models import speech_model
from .textops import is_stock_hallucination, tidy

CPU_OK_S = 3.0        # seconds per 15 s of speech: a model at least this quick on the CPU runs there itself
PREVIEW_CPU_S = 1.5   # ... and one this quick on the CPU also shows previews while you speak


def on_gpu(device: str) -> bool:
    return device in ("cuda", "vulkan")


def _short(e: BaseException) -> str:
    text = str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__
    return text[:160]


class Engine:
    def __init__(self, cfg: Config, log=print, client: str = "Voice typing") -> None:
        self.cfg = cfg
        self.log = log
        self.client = client                # who the tray's Usage tab says asked for each transcription
        self.lock = threading.RLock()       # one decode at a time; also guards load/unload
        self.model = None
        self.state = "unloaded"             # unloaded | loading | ready | failed
        self.device = ""
        self.model_name = ""
        self.note = ""                      # shown in the bubble once: why the GPU is not used, or why loading failed
        self.load_seconds = 0.0
        self.last_used = time.monotonic()
        self.force_cpu = False
        self._loader: threading.Thread | None = None

    # ---------------------------------------------------------------- loading

    def load_async(self) -> None:
        with self.lock:
            if self.state in ("ready", "loading"):
                return
            self.state = "loading"
            self._loader = threading.Thread(target=self._load, name="whisper-load", daemon=True)
            self._loader.start()

    def wait_ready(self, timeout: float | None = None) -> bool:
        if self.state in ("unloaded", "failed"):
            self.load_async()
        loader = self._loader
        if self.state == "loading" and loader is not None:
            loader.join(timeout)
        return self.state == "ready"

    def _load(self) -> None:
        t0 = time.monotonic()
        try:
            model, device, name, note = self._open()
        except Exception as e:  # noqa: BLE001 - reported in the bubble and the log
            with self.lock:
                self.state, self.note = "failed", f"{speech_model(self.cfg.model).family} could not load: {_short(e)}"
            self.log(f"[dictation] {self.note}")
            return
        with self.lock:
            self.model, self.device, self.model_name, self.note = model, device, name, note
            self.state = "ready"
            self.last_used = time.monotonic()
            self.load_seconds = time.monotonic() - t0
        self.log(f"[dictation] {self.family} {name} ready on {device} in {self.load_seconds:.1f} s{f' ({note})' if note else ''}")

    def _model(self, name: str, **kwargs):
        """Load from the Hugging Face cache without asking huggingface.co for a newer revision (faster-whisper
        otherwise does on every load: a network call that leaks the model name and stalls offline). Downloads only
        when the model is not cached yet."""
        from faster_whisper import WhisperModel

        try:
            return WhisperModel(name, local_files_only=True, **kwargs)
        except Exception as e:  # noqa: BLE001 - huggingface_hub raises different errors for "not cached"
            if "local" not in str(e).lower() and "cache" not in str(e).lower() and "not found" not in str(e).lower():
                raise
        self.log(f"[dictation] {name} is not cached yet; downloading it into the Hugging Face cache")
        return WhisperModel(name, **kwargs)

    @property
    def family(self) -> str:
        """'Whisper', 'Parakeet' or 'Canary-Qwen': the model family's name for the bubble's messages."""
        return speech_model(self.model_name or self.cfg.model).family

    @property
    def previews(self) -> bool:
        """Show a guess of the phrase while you speak: on the GPU, or on the CPU with a model quick enough there."""
        if self.state != "ready":
            return False
        if on_gpu(self.device):
            return True
        m = speech_model(self.model_name)
        return m.engine != "faster-whisper" and 0 < m.speed_cpu <= PREVIEW_CPU_S

    def _open(self):
        cfg = self.cfg
        m = speech_model(cfg.model)
        note = ""
        if not self.force_cpu and (cfg.device == "cuda" or (cfg.device == "auto" and m.device == "gpu")):
            try:
                model = self._load_model(m, gpu=True)
                return model, self._device(model, "cuda"), m.name, ""
            except Exception as e:  # noqa: BLE001
                if cfg.device == "cuda":
                    raise
                note = f"GPU not used: {_short(e)}. "
                self.log(f"[dictation] {note}falling back to the CPU")
        # On the CPU: the model itself when it is quick there (Parakeet), else the CPU model (Whisper small).
        quick = m.engine != "faster-whisper" and 0 < m.speed_cpu <= CPU_OK_S
        name = m.name if quick else (cfg.cpu_model or m.name)
        model = self._load_model(speech_model(name), gpu=False)
        if quick and not note and m.device == "cpu":
            return model, "cpu", name, ""   # its own device: nothing to explain
        return model, "cpu", name, f"{note}Running {name} on the CPU."

    @staticmethod
    def _device(model, whisper_device: str) -> str:
        return model.device if isinstance(model, stt.Backend) else whisper_device

    def _load_model(self, m, gpu: bool):
        """The model loaded and warmed on the GPU or the CPU, with its engine."""
        threads = max(1, (os.cpu_count() or 4) // 2)
        if m.engine != "faster-whisper":
            backend = stt.open_backend(m, gpu, threads, self.log)
            try:
                self._warm(backend)   # Vulkan compiles its shaders now (once per driver), not at the first dictation
            except Exception:
                backend.close()
                raise
            return backend
        cfg = self.cfg
        if gpu:
            import ctranslate2

            if ctranslate2.get_cuda_device_count() < 1:
                raise RuntimeError("no CUDA device")
            if os.name == "nt" and not _gpu.add_cuda_dlls():
                raise RuntimeError("cuBLAS 12 not found (it ships with Ollama; or install nvidia-cublas-cu12)")
            compute = cfg.compute_type if cfg.compute_type != "auto" else "int8_float16"
            model = self._model(m.name, device="cuda", compute_type=compute)
            self._warm(model)  # loads cuBLAS and cuDNN now, so the first dictation is not the slow one
            return model
        compute = cfg.compute_type if cfg.compute_type not in ("auto", "float16", "int8_float16", "bfloat16") else "int8"
        return self._model(m.name, device="cpu", compute_type=compute, cpu_threads=threads)

    def _warm(self, model) -> None:
        noise = (np.random.default_rng(0).standard_normal(16000) * 0.001).astype(np.float32)
        if isinstance(model, stt.Backend):
            model.transcribe(noise * 30, None)   # quiet noise, loud enough not to count as silence elsewhere
            return
        segments, _ = model.transcribe(noise, language="en", beam_size=1, vad_filter=False, without_timestamps=True,
                                       condition_on_previous_text=False)
        for _ in segments:
            pass

    def unload(self) -> None:
        with self.lock:
            if self.model is None:
                return
            model, self.model = self.model, None
            self.state = "unloaded"
        if isinstance(model, stt.Backend):
            model.close()   # transcribe.cpp frees its GPU memory now, not at garbage collection
        del model
        gc.collect()
        self.log(f"[dictation] {self.family} unloaded (idle); the next dictation loads it again")

    def unload_if_idle(self) -> None:
        minutes = self.cfg.unload_after_min
        if minutes and self.state == "ready" and time.monotonic() - self.last_used > minutes * 60:
            self.unload()

    # ---------------------------------------------------------------- transcription

    def transcribe(self, audio: np.ndarray, *, prompt: str = "", fast: bool = False, language: str = "",
                   client: str = "") -> tuple[str, str]:
        """(text, language) for float32 mono 16 kHz audio. `fast` (beam 1) is for previews while you speak.
        Every call is recorded for the tray's Usage tab: audio length, model and load time, tokens; never the text.
        `client` names who asked when it is not this engine's own client (Open WebUI through the transcription
        endpoint, which shares the loaded model with voice typing)."""
        t0 = time.monotonic()
        stats = {"run_s": 0.0, "tokens": 0, "language": ""}
        ready = self.state == "ready"
        load_s = 0.0
        failed = ""
        try:
            if not self.wait_ready():
                raise RuntimeError(self.note or f"{self.family} is not loaded")
            load_s = 0.0 if ready else time.monotonic() - t0
            try:
                return self._decode(audio, prompt, fast, language, stats)
            except RuntimeError as e:
                if not on_gpu(self.device) or self.cfg.device == "cuda":
                    raise
                # Out of GPU memory (ComfyUI or a bigger chat model took the card) or a driver hiccup: go to the CPU.
                self.log(f"[dictation] GPU decode failed ({_short(e)}); reloading on the CPU")
                self.unload()
                self.force_cpu = True
                t1 = time.monotonic()
                if not self.wait_ready():
                    raise
                load_s += time.monotonic() - t1
                return self._decode(audio, prompt, fast, language, stats)
        except Exception as e:
            failed = type(e).__name__  # not the message, which can name files and folders
            raise
        finally:
            self._record(audio, t0, load_s, stats, fast, failed, client or self.client)

    def _record(self, audio: np.ndarray, t0: float, load_s: float, stats: dict, fast: bool, failed: str,
                client: str) -> None:
        try:
            usage_log.record(
                "voice-typing", self.model_name or self.cfg.model, "transcription",
                client=client, status="failure" if failed else "success", error=failed,
                latency_ms=(time.monotonic() - t0) * 1000, load_ms=load_s * 1000 if load_s else None,
                run_ms=stats["run_s"] * 1000, output_tokens=stats["tokens"], audio_s=len(audio) / 16000,
                # A preview re-reads the phrase so far while you speak; the tab keeps previews out of its totals.
                detail={k: v for k, v in (("device", self.device), ("language", stats["language"]),
                                          ("preview", fast)) if v})
        except Exception as e:  # noqa: BLE001 - a usage record must never break dictation
            self.log(f"[dictation] usage record failed: {_short(e)}")

    def _decode(self, audio: np.ndarray, prompt: str, fast: bool, language: str, stats: dict) -> tuple[str, str]:
        # "auto" detects even when dictation.language names one (Open WebUI's recordings); "" follows the setting.
        if language == "auto":
            lang = None
        else:
            lang = language or (None if self.cfg.language in ("", "auto") else self.cfg.language)
        with self.lock:
            if self.model is None:
                raise RuntimeError(f"{self.family} was unloaded")
            t0 = time.monotonic()
            self.last_used = t0
            if isinstance(self.model, stt.Backend):
                # Parakeet or Canary-Qwen: no prompt or vocabulary, nothing to filter by segment.
                text, found, tokens = stt.transcribe(self.model, audio, lang)
                self.last_used = time.monotonic()
                stats["run_s"] += self.last_used - t0
                stats["tokens"] += tokens
                stats["language"] = found or ""
                text = tidy(text)
                return ("" if is_stock_hallucination(text) else text), stats["language"]
            segments, info = self.model.transcribe(
                audio, language=lang, beam_size=1 if fast else 5, vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 500, "speech_pad_ms": 200},
                condition_on_previous_text=False, without_timestamps=True,
                initial_prompt=prompt or None, hotwords=self.cfg.vocabulary or None)
            segments = list(segments)  # the model decodes while the generator runs
            self.last_used = time.monotonic()
            stats["run_s"] += self.last_used - t0
        stats["tokens"] += sum(len(getattr(s, "tokens", None) or ()) for s in segments)
        stats["language"] = getattr(info, "language", "") or ""
        texts = [s.text for s in segments if not (s.no_speech_prob > 0.6 and s.avg_logprob < -1.0)]
        text = tidy(" ".join(t.strip() for t in texts))
        if is_stock_hallucination(text):
            text = ""
        return text, stats["language"]
