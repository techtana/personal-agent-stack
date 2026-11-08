"""The voices behind read aloud: Kokoro-82M through ONNX Runtime on the GPU (CUDA) or the CPU, and Windows' own voices
through SAPI. Runs in the voice typing app's environment (numpy, onnxruntime or onnxruntime-gpu, espeakng-loader,
comtypes); speak.py holds the parts the project's tests cover without it.

Measured on the reference machine (2026-11-08):
  - CPU (Ryzen 5 5500, 6 of 12 threads): Kokoro loads in 1.2 s and speaks about 3.3x faster than real time with one
    piece at a time, 4.3x with two at once sharing the threads; fp32 (326 MB) and int8 (92 MB) alike.
  - GPU (RTX 3060, onnxruntime-gpu 1.31.1 on CUDA 13, cuDNN 9.28): about 0.3-0.4 s per sentence, 12-20x real time,
    1.0 GB of GPU memory; fp32 only (int8 runs slower there). DirectML failed on Kokoro's ConvTranspose layers.
  - Whisper transcribed Kokoro's output back word for word. A Windows voice makes 6 s of speech in 0.02-0.05 s.

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
    """Kokoro-82M: loads on first use, on the GPU (CUDA) or the CPU, and is freed after read_aloud.unload_after_min
    idle minutes. Several pieces may be made at once: ONNX Runtime sessions take concurrent runs, which share the CPU
    session's threads (two at once made 4.3x real time against 3.3x one at a time on the reference machine)."""

    CPU_THREADS = max(1, (os.cpu_count() or 4) // 2)   # half the logical processors: the rest of the PC keeps headroom

    def __init__(self, log=print) -> None:
        self.log = log
        self.lock = threading.RLock()          # guards load, unload and the voice tables; runs happen outside it
        self.session = None
        self.espeak = None
        self.vocab: dict[str, int] = {}
        self.styles: dict[str, np.ndarray] = {}
        self.variant = ""
        self.wanted = ""                       # the device asked for: auto | gpu | cpu
        self.device = ""                       # where it runs: cuda | cpu
        self.state = "unloaded"                # unloaded | loading | ready | failed
        self.note = ""                         # why the GPU is not used, or why loading failed
        self.load_seconds = 0.0
        self.last_used = time.monotonic()
        self.running = 0                       # runs in progress: never unload under them
        self.force_cpu = False                 # the GPU failed during a run (out of memory): CPU until the app restarts

    def ready(self, variant: str, device: str = "auto") -> bool:
        device = "cpu" if self.force_cpu else device
        return self.state == "ready" and self.variant == variant and self.wanted == device

    @staticmethod
    def gpu_available() -> bool:
        """onnxruntime-gpu is installed (read aloud's GPU option) and offers CUDA."""
        try:
            import onnxruntime as ort

            return "CUDAExecutionProvider" in ort.get_available_providers()
        except Exception:  # noqa: BLE001
            return False

    def _session(self, path: str, use_gpu: bool):
        import onnxruntime as ort

        so = ort.SessionOptions()
        so.log_severity_level = 3              # ScatterND's "reduction none" notice on every load is not news
        so.inter_op_num_threads = 1
        so.add_session_config_entry("session.intra_op.allow_spinning", "0")  # idle threads sleep
        if use_gpu:
            so.intra_op_num_threads = 1
            return ort.InferenceSession(path, so, providers=[("CUDAExecutionProvider", {"device_id": 0}),
                                                              "CPUExecutionProvider"])
        so.intra_op_num_threads = self.CPU_THREADS
        return ort.InferenceSession(path, so, providers=["CPUExecutionProvider"])

    def load(self, variant: str, device: str = "auto") -> float:
        """Load (or switch to) the weights on the device asked for; returns the seconds it took, 0 when they were
        loaded already. "auto" and "gpu" use CUDA when onnxruntime-gpu and its libraries are there, else the CPU,
        with a note saying why."""
        device = "cpu" if self.force_cpu else device
        with self.lock:
            if self.ready(variant, device):
                return 0.0
            while self.running:                # a switch waits for runs on the old session to end
                self.lock.release()
                time.sleep(0.02)
                self.lock.acquire()
            self.unload(quiet=True)
            self.state = "loading"
            t0 = time.monotonic()
            note = ""
            try:
                from . import gpu
                from .espeak import Espeak

                self.espeak = self.espeak or Espeak()
                tokenizer = json.loads(kokoro_file("tokenizer.json", download=False).read_text(encoding="utf-8"))
                self.vocab = dict(tokenizer["model"]["vocab"])
                path = str(kokoro_file(speak.KOKORO_FILES[variant], download=False))
                use_gpu = device != "cpu" and not self.force_cpu
                if use_gpu and variant != "fp32":
                    note, use_gpu = "the int8 weights are slower on the GPU than on the CPU", False
                elif use_gpu and not self.gpu_available():
                    note, use_gpu = ("its GPU libraries are not installed (Runs on: gpu, then `stack.py read-aloud "
                                      "install`)"), False
                elif use_gpu and not gpu.add_kokoro_cuda_dlls():
                    note, use_gpu = "cuDNN 9 or Ollama's CUDA 13 libraries were not found", False
                elif self.force_cpu:
                    note = "the GPU failed earlier (out of memory?), so Kokoro stays on the CPU until voice typing restarts"
                session = None
                if use_gpu:
                    try:
                        session = self._session(path, True)
                        if "CUDAExecutionProvider" not in session.get_providers():
                            note, session = "CUDA did not start (see the log)", None
                    except Exception as e:  # noqa: BLE001 - fall back to the CPU
                        note, session = f"CUDA did not start: {_short(e)}", None
                self.session = session or self._session(path, False)
                self.device = "cuda" if session is not None else "cpu"
            except Exception as e:  # noqa: BLE001 - shown in the bubble; Windows voices still work
                self.state, self.note = "failed", f"Kokoro could not load: {_short(e)}"
                self.session = None
                self.log(f"[read] {self.note}")
                raise SpeechError(self.note) from e
            self.variant, self.wanted, self.state = variant, device, "ready"
            self.note = f"GPU not used: {note}" if note and device == "gpu" else note
            self.load_seconds = time.monotonic() - t0
            self.last_used = time.monotonic()
            where = "the GPU" if self.device == "cuda" else f"the CPU ({self.CPU_THREADS} threads)"
            self.log(f"[read] Kokoro ({variant}) ready on {where} in {self.load_seconds:.1f} s, espeak-ng "
                     f"{self.espeak.version}{f'; {note}' if note else ''}")
            return self.load_seconds

    def unload(self, quiet: bool = False) -> None:
        with self.lock:
            if self.session is None or self.running:
                return
            self.session = None
            self.styles.clear()
            self.state = "unloaded"
        gc.collect()
        if not quiet:
            self.log("[read] Kokoro unloaded (idle); the next reading loads it again")

    def unload_if_idle(self, minutes: float) -> None:
        if minutes and self.state == "ready" and not self.running and time.monotonic() - self.last_used > minutes * 60:
            self.unload()

    def _style(self, voice_id: str) -> np.ndarray:
        with self.lock:
            table = self.styles.get(voice_id)
            if table is None:
                table = np.fromfile(kokoro_file(f"voices/{voice_id}.bin"), dtype=np.float32).reshape(-1, 1, 256)
                self.styles[voice_id] = table
            return table

    def phonemes(self, text: str, language: str) -> str:
        parts = [piece if punct else self.espeak.phonemes(piece, language)
                 for punct, piece in speak.split_punctuation(speak.for_phonemes(text, language))]
        return speak.tidy_phonemes("".join(parts), language)

    def synth(self, text: str, voice: Voice, speed: float, variant: str, device: str = "auto") -> Audio:
        load_s = self.load(variant, device)
        with self.lock:
            session = self.session
            if session is None:
                raise SpeechError("Kokoro was unloaded")
            self.running += 1
        try:
            t0 = time.monotonic()
            self.last_used = t0
            table = self._style(voice.id)
            ps = self.phonemes(text, voice.language)
            chunks, tokens = [], 0
            for ids in speak.split_ids(ps, self.vocab):
                style = table[min(len(ids), len(table) - 1)]
                feeds = {"input_ids": np.array([[0, *ids, 0]], dtype=np.int64), "style": style.astype(np.float32),
                         "speed": np.array([speed], dtype=np.float32)}
                try:
                    wav = session.run(None, feeds)[0]
                except Exception as e:  # noqa: BLE001 - the GPU ran out of memory (ComfyUI took it), or a driver hiccup
                    if self.device != "cuda":
                        raise
                    self.log(f"[read] GPU run failed ({_short(e)}); Kokoro moves to the CPU")
                    self.force_cpu = True
                    with self.lock:
                        self.running -= 1
                    try:
                        load_s += self.load(variant, "cpu")
                    finally:
                        with self.lock:
                            self.running += 1
                            session = self.session
                    wav = session.run(None, feeds)[0]
                chunks.append(np.asarray(wav, dtype=np.float32).reshape(-1))
                tokens += len(ids)
            self.last_used = time.monotonic()
            run_s = self.last_used - t0
        finally:
            with self.lock:
                self.running -= 1
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
        return voice.engine != "kokoro" or self.kokoro.ready(cfg.kokoro, cfg.device)

    def warm(self, cfg: speak.Config) -> None:
        """Load Kokoro now when the chosen voice is one of its own (a click is coming: the pointer is on the speaker
        button, or a reading is copying the selection), so the first sentence does not wait for the load."""
        if cfg.kokoro == "off" or not speak.kokoro_voice(cfg.voice) or self.kokoro.ready(cfg.kokoro, cfg.device):
            return
        if self.kokoro.state == "loading" or not self.kokoro_installed() or not self.kokoro_downloaded(cfg.kokoro):
            return
        try:
            self.kokoro.load(cfg.kokoro, cfg.device)
        except SpeechError:
            pass   # the reading reports it

    def workers(self, voice: Voice) -> int:
        """Pieces made at once: two on the CPU, which share Kokoro's threads (about 30% more speech per second, and no
        more processors than one run uses); one on the GPU (fast enough) and for Windows voices (instant)."""
        return 2 if voice.engine == "kokoro" and self.kokoro.device != "cuda" else 1

    def lookahead_s(self, voice: Voice) -> float:
        """Seconds of speech to prepare ahead of what plays: more on the GPU, where it costs little."""
        return 60.0 if voice.engine != "kokoro" or self.kokoro.device == "cuda" else 30.0

    def synth(self, text: str, voice: Voice, speed: float, cfg: speak.Config) -> Audio:
        if voice.engine == "kokoro":
            if cfg.kokoro == "off":
                raise SpeechError("Kokoro is off (read_aloud.kokoro)")
            return self.kokoro.synth(text, voice, speed, cfg.kokoro, cfg.device)
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
                                          ("device", self.kokoro.device if voice.engine == "kokoro" else "cpu"),
                                          ("speed", cfg.speed), ("stopped", stopped)) if v})
        except Exception as e:  # noqa: BLE001 - a usage record must never break reading
            self.log(f"[read] usage record failed: {_short(e)}")

    def unload_if_idle(self, minutes: float) -> None:
        self.kokoro.unload_if_idle(minutes)

    def health(self) -> dict:
        k = self.kokoro
        return {"engine": k.state, "model": f"kokoro-82m {k.variant}".strip() if k.variant else "",
                "device": k.device or "", "note": k.note, "idle_s": round(time.monotonic() - k.last_used),
                "gpu_installed": k.gpu_available()}


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
