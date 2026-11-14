"""Speech-to-text engines besides faster-whisper, for voice typing's Engine (engine.py), which records every call for the
tray's Usage tab:

- OnnxAsr: NVIDIA Parakeet TDT 0.6B v3 through onnx-asr (pure Python, MIT) on the ONNX Runtime voice typing already has.
  Its int8 weights run faster on the CPU than with CUDA (measured on the reference PC, 2026-11-09: 7.5 s of speech in
  0.31 s on 6 threads, 0.41 s with CUDA), so dictation.device auto keeps it on the CPU, where it holds no GPU memory.
- TranscribeCpp: NVIDIA Canary-Qwen 2.5B through transcribe.cpp (ggml, MIT) with its prebuilt Vulkan library: 7.5 s in
  0.28 s on the RTX 3060 with 3.3 GB of GPU memory, but only 2x real time on the CPU. The very first run on a GPU
  compiles Vulkan shaders (20 s on the reference PC); the driver keeps them, so Engine warms the model at load.

Both take 16 kHz mono float32. Voice typing sends phrases of 25 s or less; Open WebUI's microphone sends whole files, so
transcribe() cuts long audio at its quietest moments into pieces of at most MAX_PIECE_S (Canary-Qwen was trained on up
to 40 s, and onnx-asr reads 20-30 s at most without a VAD). Model files come from the Hugging Face cache at the catalog's
pinned revision, downloaded (and checked against their sha256) only when missing.
"""
from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path

import numpy as np

from .models import SpeechModel

RATE = 16000
MAX_PIECE_S = 25.0      # longest piece one call reads
SEARCH_S = 8.0          # where a cut may go: the quietest moment in the last SEARCH_S seconds of a piece
WINDOW_S = 0.1          # loudness is compared over windows this long
SILENT_DBFS = -55.0     # a piece quieter than this throughout is skipped (no words to find, and LLM decoders invent some)


class SttError(RuntimeError):
    """The engine or its model cannot load here; the message says why, for the bubble and the log."""


# ---------------------------------------------------------------- model files

def hf_home() -> Path:
    return Path(os.environ.get("HF_HOME") or Path.home() / ".cache" / "huggingface")


def snapshot_dir(m: SpeechModel, home: Path | None = None) -> Path:
    """The pinned revision's folder in the Hugging Face cache."""
    return (home or hf_home()) / "hub" / f"models--{m.repo.replace('/', '--')}" / "snapshots" / m.revision


def missing_files(m: SpeechModel, home: Path | None = None) -> list[str]:
    snap = snapshot_dir(m, home)
    return [name for name in m.files if not (snap / name).is_file()]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def fetch(m: SpeechModel, report=lambda *a: None) -> Path:
    """Download the model's missing files at its pinned revision into the Hugging Face cache, check each pinned sha256,
    and return the snapshot folder. A file that does not match is deleted, so the next try downloads it again."""
    if not m.revision or not m.files:
        raise SttError(f"{m.name} has no pinned files in config/installer.yaml")
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    from huggingface_hub import hf_hub_download

    todo = missing_files(m)
    for i, name in enumerate(todo):
        report(f"downloading {m.label}: {name} ({i + 1} of {len(todo)})")
        path = Path(hf_hub_download(m.repo, name, revision=m.revision))
        want = m.files.get(name)
        if want and sha256(path) != want:
            real = path.resolve()   # with symlinks the snapshot entry points at blobs/<etag>: delete both
            path.unlink(missing_ok=True)
            if real != path:
                real.unlink(missing_ok=True)
            raise SttError(f"{name} of {m.label} does not match its pinned sha256 (deleted); try again")
    return snapshot_dir(m)


def model_dir(m: SpeechModel, download: bool = True, log=print) -> Path:
    """The snapshot folder with every file the model needs; downloads what is missing unless download is False."""
    if missing_files(m):
        if not download:
            raise SttError(f"{m.label} is not downloaded yet")
        log(f"[dictation] {m.label} is not downloaded yet; fetching it into {hf_home()}")
        fetch(m, lambda text, *_: log(f"[dictation] {text}"))
    return snapshot_dir(m)


# ---------------------------------------------------------------- long audio

def _dbfs(x: np.ndarray) -> float:
    rms = float(np.sqrt(np.mean(np.square(x, dtype=np.float64)))) if x.size else 0.0
    return 20 * math.log10(rms + 1e-9)


def is_silent(audio: np.ndarray) -> bool:
    """No window of the piece is louder than SILENT_DBFS."""
    w = max(1, int(WINDOW_S * RATE))
    n = len(audio) // w
    if n == 0:
        return _dbfs(audio) < SILENT_DBFS
    frames = audio[: n * w].reshape(n, w).astype(np.float64)
    loudest = float(np.sqrt(np.max(np.mean(frames * frames, axis=1))))
    return 20 * math.log10(loudest + 1e-9) < SILENT_DBFS


def split(audio: np.ndarray, max_s: float = MAX_PIECE_S, search_s: float = SEARCH_S) -> list[np.ndarray]:
    """Pieces of at most max_s seconds, each cut at the quietest WINDOW_S window of its last search_s seconds, so a cut
    falls between words where there is a pause. Short audio comes back whole."""
    limit = int(max_s * RATE)
    if len(audio) <= limit:
        return [audio]
    w = max(1, int(WINDOW_S * RATE))
    pieces, start = [], 0
    while len(audio) - start > limit:
        lo = start + max(w, limit - int(search_s * RATE))
        hi = start + limit
        region = audio[lo:hi].astype(np.float64)
        n = len(region) // w
        if n > 0:
            energy = np.mean(region[: n * w].reshape(n, w) ** 2, axis=1)
            cut = lo + int(np.argmin(energy)) * w + w // 2
        else:
            cut = hi
        pieces.append(audio[start:cut])
        start = cut
    pieces.append(audio[start:])
    return pieces


# ---------------------------------------------------------------- engines

class Backend:
    """One loaded model. transcribe() returns (text, language code or '', tokens decoded or 0)."""
    device = "cpu"          # cpu | cuda | vulkan

    def __init__(self, m: SpeechModel):
        self.m = m

    def transcribe(self, audio: np.ndarray, language: str | None) -> tuple[str, str, int]:
        raise NotImplementedError

    def close(self) -> None:
        pass


class OnnxAsr(Backend):
    """A model onnx-asr runs on ONNX Runtime (Parakeet TDT). on_gpu uses CUDA, which needs onnxruntime-gpu and cuDNN 9
    for CUDA 13 (read aloud's GPU option installs both) and Ollama's CUDA 13 runtime."""

    def __init__(self, m: SpeechModel, on_gpu: bool, threads: int, log=print):
        super().__init__(m)
        import onnx_asr
        import onnxruntime as rt

        providers = ["CPUExecutionProvider"]
        if on_gpu:
            from . import gpu

            if "CUDAExecutionProvider" not in rt.get_available_providers():
                raise SttError("ONNX Runtime here has no CUDA (onnxruntime-gpu is not installed)")
            if os.name == "nt" and not gpu.add_kokoro_cuda_dlls():
                raise SttError("cuDNN 9 or the CUDA 13 runtime was not found (read aloud's GPU option installs them)")
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        opts = rt.SessionOptions()
        opts.intra_op_num_threads = max(1, threads)
        opts.log_severity_level = 3   # errors only: the CUDA provider warns about copy nodes on every load
        self.model = onnx_asr.load_model(m.onnx_asr, str(model_dir(m, log=log)), quantization=m.quantization or None,
                                         providers=providers, sess_options=opts)
        self.device = "cuda" if on_gpu else "cpu"

    def transcribe(self, audio: np.ndarray, language: str | None) -> tuple[str, str, int]:
        # Parakeet TDT v3 finds the language itself: it takes no language hint.
        return str(self.model.recognize(audio, sample_rate=RATE) or ""), "", 0


_log_routed = False


def _route_native_log(log) -> None:
    """transcribe.cpp's own warnings and errors into voice typing's log, once per process (its info lines, one per
    tensor block, would flood it)."""
    global _log_routed
    if _log_routed:
        return
    import transcribe_cpp as tc

    tc.set_log_callback(lambda level, msg: log(f"[dictation] transcribe.cpp: {msg.strip()}") if level in (2, 3) and
                        msg.strip() else None)
    _log_routed = True


class TranscribeCpp(Backend):
    """A model transcribe.cpp runs from one GGUF file (Canary-Qwen 2.5B). on_gpu uses its Vulkan library, which runs on
    any card whose driver ships Vulkan; otherwise its CPU library (the variant for this CPU is picked at load)."""

    def __init__(self, m: SpeechModel, on_gpu: bool, threads: int, log=print):
        super().__init__(m)
        import transcribe_cpp as tc

        _route_native_log(log)
        backend = "vulkan" if on_gpu else "cpu"
        if on_gpu and not tc.backend_available("vulkan"):
            raise SttError("no Vulkan device (the graphics driver ships Vulkan; update it)")
        path = model_dir(m, log=log) / (m.model_file or next(iter(m.files)))
        self.model = tc.Model(str(path), backend=backend)
        try:
            self.session = self.model.session(n_ctx=m.n_ctx, n_threads=max(1, threads))
        except Exception:
            self.model.close()
            raise
        self.device = backend
        langs = set(self.model.capabilities.languages or ())
        self.languages = langs or set(m.languages)

    def transcribe(self, audio: np.ndarray, language: str | None) -> tuple[str, str, int]:
        if language and language not in self.languages:
            language = None
        if language is None and self.languages == {"en"}:
            language = "en"   # Canary-Qwen transcribes English only and detects nothing
        r = self.session.run(np.ascontiguousarray(audio, dtype=np.float32), language=language)
        return r.text.strip(), r.language or (language or ""), len(r.tokens)

    def close(self) -> None:
        for part in (getattr(self, "session", None), getattr(self, "model", None)):
            try:
                if part is not None:
                    part.close()
            except Exception:  # noqa: BLE001 - freeing is best effort; the process may be ending
                pass


ENGINES = {"onnx-asr": OnnxAsr, "transcribe.cpp": TranscribeCpp}


def open_backend(m: SpeechModel, on_gpu: bool, threads: int, log=print) -> Backend:
    """Load the model with its engine on the GPU or the CPU; raises with a short reason when it cannot here."""
    cls = ENGINES.get(m.engine)
    if cls is None:
        raise SttError(f"{m.label}: engine {m.engine!r} is not one voice typing runs here")
    module = {"onnx-asr": "onnx_asr", "transcribe.cpp": "transcribe_cpp"}[m.engine]
    try:
        __import__(module)
    except ImportError as e:
        raise SttError(f"{m.label} needs {m.engine} in voice typing's environment; run the installer again "
                       f"(Voice typing > Repair) or `uv run scripts/stack.py dictate install` ({e})") from e
    return cls(m, on_gpu, threads, log)


def transcribe(backend: Backend, audio: np.ndarray, language: str | None) -> tuple[str, str, int]:
    """The whole recording through the backend, piece by piece; silent pieces are skipped."""
    texts, lang, tokens = [], "", 0
    for piece in split(audio):
        if len(piece) < RATE // 10 or is_silent(piece):
            continue
        try:
            text, piece_lang, n = backend.transcribe(piece, language)
        except SttError:
            raise
        except Exception as e:  # noqa: BLE001 - onnxruntime and transcribe.cpp have their own types; the engine
            raise SttError(f"{backend.m.label} failed: {e}") from e   # falls back to the CPU on a RuntimeError
        if text:
            texts.append(text)
        lang = lang or piece_lang
        tokens += n
    return " ".join(texts), lang, tokens
