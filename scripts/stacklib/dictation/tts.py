"""The voices behind read aloud: Kokoro-82M through ONNX Runtime on the GPU (CUDA) or the CPU, Kokoro v1.1-zh for
Mandarin the same way (phonemes from misaki instead of espeak-ng), Piper voices for more languages through the same ONNX
Runtime on the CPU, and Windows' own voices through SAPI. Runs in the voice typing app's environment (numpy,
onnxruntime or onnxruntime-gpu, espeakng-loader, comtypes; misaki[zh] with the Mandarin voices); speak.py holds the
parts the project's tests cover without it.

Measured on the reference machine (2026-11-08):
  - CPU (Ryzen 5 5500, 6 of 12 threads): Kokoro loads in 1.2 s and speaks about 3.3x faster than real time with one
    piece at a time, 4.3x with two at once sharing the threads; fp32 (326 MB) and int8 (92 MB) alike.
  - GPU (RTX 3060, onnxruntime-gpu 1.31.1 on CUDA 13, cuDNN 9.28): about 0.3-0.4 s per sentence, 12-20x real time,
    1.0 GB of GPU memory; fp32 only (int8 runs slower there). DirectML failed on Kokoro's ConvTranspose layers.
  - Whisper transcribed Kokoro's output back word for word. A Windows voice makes 6 s of speech in 0.02-0.05 s.
  - Kokoro v1.1-zh (Mandarin): about 3.2x real time on the CPU (one piece at a time) with fp32 and int8 alike, 10x on
    the GPU (0.5 s per sentence once warm); loading takes about 2 s, misaki's dictionaries (1.3 s; 10 s on the first
    run after an install, while Smart App Control checks them) beside the ONNX session.

Every reading is one usage record (source read-aloud, kind speech) for the tray's Usage tab: seconds of speech, the
time the voice worked, phoneme tokens, the voice; never the text.
"""
from __future__ import annotations

import gc
import json
import os
import re
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


TRIM_LEVEL = 0.01       # quieter than this counts as silence (about -40 dBFS)
TRIM_MARGIN_S = 0.04    # silence kept at each end, so a word's first and last sound are not clipped


def trim(pcm: bytes, rate: int = SAMPLE_RATE) -> bytes:
    """16-bit PCM without the silence a voice puts around a sentence (measured 2026-11-08: Kokoro 0.25-0.36 s before
    and 0.4-0.7 s after, a Windows voice 0.1 s before and 0.77 s after), keeping TRIM_MARGIN_S at each end."""
    x = np.frombuffer(pcm, dtype="<i2")
    loud = np.flatnonzero(np.abs(x.astype(np.int32)) > int(TRIM_LEVEL * 32768))
    if not len(loud):
        return pcm
    margin = int(TRIM_MARGIN_S * rate)
    a, b = max(0, loud[0] - margin), min(len(x), loud[-1] + 1 + margin)
    return x[a:b].tobytes()


def _pcm16(audio: np.ndarray) -> bytes:
    return (np.clip(audio, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()


_ESPEAK = None
_ESPEAK_LOCK = threading.Lock()


def shared_espeak():
    """One espeak-ng for every voice that needs phonemes (it keeps global state; its calls hold one lock)."""
    global _ESPEAK
    with _ESPEAK_LOCK:
        if _ESPEAK is None:
            from .espeak import Espeak

            _ESPEAK = Espeak()
        return _ESPEAK


def resample(audio: np.ndarray, src: int, dst: int = SAMPLE_RATE) -> np.ndarray:
    """Linear resampling to the player's rate (Piper speaks at 22.05 kHz, the player plays 24 kHz): plain
    interpolation, inaudible for speech at this ratio."""
    if src == dst or not len(audio):
        return audio.astype(np.float32)
    n = int(round(len(audio) * dst / src))
    return np.interp(np.arange(n) * (src / dst), np.arange(len(audio)), audio).astype(np.float32)


# ---------------------------------------------------------------- Kokoro

def hf_file(repo: str, revision: str, name: str, download: bool = True) -> Path:
    """A file of a pinned repository from the Hugging Face cache; downloaded only when it is not there yet
    (huggingface_hub would otherwise ask huggingface.co for the newest revision every time)."""
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    from huggingface_hub import hf_hub_download

    try:
        return Path(hf_hub_download(repo, name, revision=revision, local_files_only=True))
    except Exception:  # noqa: BLE001 - LocalEntryNotFoundError and friends: not cached yet
        if not download:
            raise
    return Path(hf_hub_download(repo, name, revision=revision))


def kokoro_file(name: str, download: bool = True) -> Path:
    """A file of the pinned Kokoro v1.0 repository (config/installer.yaml kokoro)."""
    return hf_file(speak.KOKORO_REPO, speak.KOKORO_REVISION, name, download)


def zh_file(name: str, download: bool = False) -> Path:
    """A file of the pinned Kokoro v1.1-zh repository (config/installer.yaml kokoro_zh); reading never downloads."""
    return hf_file(speak.ZH_REPO, speak.ZH_REVISION, name, download)


def zh_cached(variant: str) -> bool:
    """The Mandarin weights of this variant, the tokenizer and every offered voice are in the Hugging Face cache."""
    try:
        for name in speak.zh_files(variant):
            zh_file(name)
        return True
    except Exception:  # noqa: BLE001
        return False


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
    LABEL = "Kokoro"

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

    # The model's files and the text front-end: KokoroZh (Mandarin) has its own.
    def _file(self, name: str) -> Path:
        return kokoro_file(name, download=False)

    def _weights(self, variant: str) -> Path:
        return self._file(speak.KOKORO_FILES[variant])

    def _voice_file(self, voice_id: str) -> Path:
        return kokoro_file(f"voices/{voice_id}.bin")

    def _prepare(self) -> None:
        """Start loading what the phonemes need besides espeak-ng, while the session loads (nothing for Kokoro v1.0)."""

    def _prepared(self) -> None:
        """Wait for what _prepare started; raise when it failed."""

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

                self._prepare()
                self.espeak = self.espeak or shared_espeak()
                tokenizer = json.loads(self._file("tokenizer.json").read_text(encoding="utf-8"))
                self.vocab = dict(tokenizer["model"]["vocab"])
                path = str(self._weights(variant))
                use_gpu = device != "cpu" and not self.force_cpu
                if use_gpu and variant != "fp32":
                    note, use_gpu = "the int8 weights are slower on the GPU than on the CPU", False
                elif use_gpu and not self.gpu_available():
                    note, use_gpu = ("its GPU libraries are not installed (Runs on: gpu, then `stack.py read-aloud "
                                      "install`)"), False
                elif use_gpu and not gpu.add_kokoro_cuda_dlls():
                    note, use_gpu = "cuDNN 9 or Ollama's CUDA 13 libraries were not found", False
                elif self.force_cpu:
                    note = (f"the GPU failed earlier (out of memory?), so {self.LABEL} stays on the CPU until voice "
                            "typing restarts")
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
                self._prepared()
            except Exception as e:  # noqa: BLE001 - shown in the bubble; Windows voices still work
                self.state, self.note = "failed", f"{self.LABEL} could not load: {_short(e)}"
                self.session = None
                self.log(f"[read] {self.note}")
                raise SpeechError(self.note) from e
            self.variant, self.wanted, self.state = variant, device, "ready"
            self.note = f"GPU not used: {note}" if note and device == "gpu" else note
            self.load_seconds = time.monotonic() - t0
            self.last_used = time.monotonic()
            where = "the GPU" if self.device == "cuda" else f"the CPU ({self.CPU_THREADS} threads)"
            self.log(f"[read] {self.LABEL} ({variant}) ready on {where} in {self.load_seconds:.1f} s, espeak-ng "
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
            self.log(f"[read] {self.LABEL} unloaded (idle); the next reading loads it again")

    def unload_if_idle(self, minutes: float) -> None:
        if minutes and self.state == "ready" and not self.running and time.monotonic() - self.last_used > minutes * 60:
            self.unload()

    def _style(self, voice_id: str) -> np.ndarray:
        with self.lock:
            table = self.styles.get(voice_id)
            if table is None:
                table = np.fromfile(self._voice_file(voice_id), dtype=np.float32).reshape(-1, 1, 256)
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
                    self.log(f"[read] GPU run failed ({_short(e)}); {self.LABEL} moves to the CPU")
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


def zh_g2p(english):
    """misaki's Mandarin G2P, version 1.1 (the phonemes Kokoro v1.1-zh was trained on): jieba cuts the words, pypinyin
    and misaki's tone rules give zhuyin-like phonemes and tone digits, cn2an reads numbers out; `english` phonemizes
    the English words found inside Chinese text."""
    import logging

    import jieba
    from misaki import zh

    jieba.setLogLevel(logging.WARNING)   # no "Building prefix dict" lines in the app's log
    return zh.ZHG2P(version="1.1", unk="", en_callable=english)


class KokoroZh(Kokoro):
    """Kokoro v1.1-zh for Mandarin (config/installer.yaml kokoro_zh): its own weights, tokenizer and voices from the
    Hugging Face cache, never downloaded while reading, and misaki's Mandarin G2P instead of espeak-ng (espeak-ng still
    reads the English words inside Chinese text). Loads on first use like Kokoro, misaki's dictionaries with it, on the
    GPU or the CPU, and is freed after the same idle minutes."""

    LABEL = "Kokoro zh"

    def __init__(self, log=print) -> None:
        super().__init__(log)
        self.g2p = None
        self.g2p_lock = threading.Lock()   # jieba and misaki keep module state: one sentence at a time (1-5 ms each)
        self._g2p_thread: threading.Thread | None = None
        self._g2p_error = ""

    def _file(self, name: str) -> Path:
        return zh_file(name)

    def _weights(self, variant: str) -> Path:
        return zh_file(speak.ZH_FILES[variant])

    def _voice_file(self, voice_id: str) -> Path:
        return zh_file(f"voices/{voice_id.removeprefix(speak.ZH_PREFIX)}.bin")

    def _make_g2p(self) -> None:
        try:
            g2p = zh_g2p(self._english)
            with self.g2p_lock:
                g2p("你好。")             # jieba builds its word index on the first sentence: here, not in a reading
            self.g2p = g2p
        except Exception as e:  # noqa: BLE001 - reported by _prepared, in the load's own error
            self._g2p_error = f"misaki did not load: {_short(e)}"

    def _prepare(self) -> None:
        """misaki's dictionaries (about 1.3 s, and jieba's index) load in a thread of their own while the ONNX session
        loads, so the first Mandarin reading waits for the slower of the two, not both."""
        if self.g2p is None and not (self._g2p_thread and self._g2p_thread.is_alive()):
            self._g2p_error = ""
            self._g2p_thread = threading.Thread(target=self._make_g2p, name="read-aloud-zh-g2p", daemon=True)
            self._g2p_thread.start()

    def _prepared(self) -> None:
        if self._g2p_thread is not None:
            self._g2p_thread.join()
        if self.g2p is None:
            raise SpeechError(self._g2p_error or "misaki did not load")

    def _english(self, text: str) -> str:
        """espeak-ng's US English phonemes for the English words in Chinese text, as Kokoro reads English."""
        return speak.tidy_phonemes(self.espeak.phonemes(text, "en-us"), "en-us")

    def phonemes(self, text: str, language: str) -> str:
        with self.g2p_lock:
            ps, _ = self.g2p(speak.for_zh(text))
        return ps


# ---------------------------------------------------------------- Piper voices

piper_ids = speak.piper_ids


class Piper:
    """Piper (VITS) voices from config/installer.yaml voice_packs, downloaded into read_aloud.packs_dir: espeak-ng IPA
    (the voice's own espeak voice, punctuation put back as Piper was trained), then ONNX Runtime on the CPU. Each voice
    loads on first use (60-115 MB, well under a second) and is freed with Kokoro after read_aloud.unload_after_min
    idle minutes."""

    CPU_THREADS = Kokoro.CPU_THREADS

    def __init__(self, log=print) -> None:
        self.log = log
        self.lock = threading.RLock()
        self.loaded: dict[str, tuple[object, dict]] = {}   # voice file -> (session, its .onnx.json)
        self.last_used = time.monotonic()
        self.running = 0

    def load(self, key: str, packs_dir: str) -> tuple[object, dict, float]:
        with self.lock:
            if key in self.loaded:
                session, config = self.loaded[key]
                return session, config, 0.0
            if not speak.pack_installed(packs_dir, key):
                raise SpeechError(f"the voice {key} is not downloaded; Download it on the tray's Features card")
            t0 = time.monotonic()
            import onnxruntime as ort

            model, conf = (Path(packs_dir) / key / name for name in speak.pack_files(key))
            config = json.loads(conf.read_text(encoding="utf-8"))
            so = ort.SessionOptions()
            so.log_severity_level = 3
            so.inter_op_num_threads = 1
            so.intra_op_num_threads = self.CPU_THREADS
            so.add_session_config_entry("session.intra_op.allow_spinning", "0")
            try:
                session = ort.InferenceSession(str(model), so, providers=["CPUExecutionProvider"])
            except Exception as e:  # noqa: BLE001 - shown in the bubble
                raise SpeechError(f"the voice {key} could not load: {_short(e)}") from e
            self.loaded[key] = (session, config)
            took = time.monotonic() - t0
            self.log(f"[read] Piper voice {key} ready in {took:.1f} s")
            return session, config, took

    def phonemes(self, text: str, voice: Voice, config: dict) -> str:
        """espeak-ng IPA in the voice's espeak language, with the punctuation Piper reads pauses and questions from."""
        espeak = shared_espeak()
        language = str((config.get("espeak") or {}).get("voice") or speak.family(voice.language))
        parts = [piece if punct else espeak.phonemes(piece, language)
                 for punct, piece in speak.split_punctuation(speak.for_phonemes(text, voice.language))]
        ps = re.sub(r"\([a-z-]{2,10}\)", "", "".join(parts))   # language-switch marks such as (en)
        return ps.replace("«", "").replace("»", "")

    def synth(self, text: str, voice: Voice, speed: float, packs_dir: str) -> Audio:
        key, speaker = speak.piper_key(voice.id)
        session, config, load_s = self.load(key, packs_dir)
        with self.lock:
            self.running += 1
        try:
            t0 = time.monotonic()
            self.last_used = t0
            ids = piper_ids(self.phonemes(text, voice, config), config.get("phoneme_id_map") or {})
            inf = config.get("inference") or {}
            feeds = {"input": np.array([ids], dtype=np.int64), "input_lengths": np.array([len(ids)], dtype=np.int64),
                     "scales": np.array([float(inf.get("noise_scale", 0.667)),
                                         float(inf.get("length_scale", 1.0)) / max(speed, 0.1),
                                         float(inf.get("noise_w", 0.8))], dtype=np.float32)}
            if int(config.get("num_speakers") or 1) > 1:
                feeds["sid"] = np.array([speaker], dtype=np.int64)
            try:
                wav = np.asarray(session.run(None, feeds)[0], dtype=np.float32).reshape(-1)
            except Exception as e:  # noqa: BLE001 - shown in the bubble
                raise SpeechError(f"the voice {voice.name} failed: {_short(e)}") from e
            audio = resample(wav, int((config.get("audio") or {}).get("sample_rate") or 22050))
            self.last_used = time.monotonic()
            run_s = self.last_used - t0
        finally:
            with self.lock:
                self.running -= 1
        return Audio(_pcm16(audio), len(audio) / SAMPLE_RATE, len(ids), run_s, load_s)

    def unload_if_idle(self, minutes: float) -> None:
        with self.lock:
            if minutes and self.loaded and not self.running and time.monotonic() - self.last_used > minutes * 60:
                names = ", ".join(self.loaded)
                self.loaded.clear()
                self.log(f"[read] Piper voices unloaded (idle): {names}")
        gc.collect()


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
        self.kokoro_zh = KokoroZh(log)
        self.piper = Piper(log)
        self._piper_voices: tuple[float, str, list[Voice]] = (-1e9, "", [])
        self.windows = WindowsVoices()
        self._win_voices: tuple[float, list[Voice]] = (-1e9, [])
        self._cached: dict[str, tuple[float, bool]] = {}   # Kokoro variant -> (checked at, files on disk)
        self._zh_cached: tuple[float, list[str]] = (-1e9, [])   # Mandarin variants downloaded, and when checked
        self._modules: dict[str, tuple[float, bool]] = {}

    def _has(self, module: str) -> bool:
        """A package of read aloud is in this environment (the installer's Read aloud feature adds them). A package that
        was missing is looked for again after a minute: the Mandarin voices' Download adds misaki while the app runs."""
        at, found = self._modules.get(module, (-1e9, False))
        if not found and time.monotonic() - at > 60:
            import importlib
            import importlib.util

            importlib.invalidate_caches()
            found = importlib.util.find_spec(module) is not None
            self._modules[module] = (time.monotonic(), found)
        return found

    def _engine(self, voice: Voice) -> Kokoro | None:
        return {"kokoro": self.kokoro, "kokoro-zh": self.kokoro_zh}.get(voice.engine)

    def zh_variants(self) -> list[str]:
        """The Mandarin weights downloaded with all their files (checked once a minute)."""
        at, have = self._zh_cached
        if time.monotonic() - at > 60:
            have = [v for v in speak.ZH_FILES if zh_cached(v)]
            self._zh_cached = (time.monotonic(), have)
        return have

    def zh_installed(self) -> bool:
        """The Mandarin voices can speak: misaki and jieba are in this environment, Kokoro's espeak-ng and ONNX Runtime
        too, and a variant of the weights is downloaded."""
        return (bool(speak.ZH_VOICES) and self.kokoro_installed() and self._has("misaki") and self._has("jieba")
                and bool(self.zh_variants()))

    def zh_variant(self, cfg: speak.Config) -> str:
        return speak.zh_variant(cfg.kokoro, self.zh_variants())

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
        """Kokoro's voices (when installed, downloaded and not turned off or broken), the Mandarin ones when their set
        is downloaded, the Piper voices downloaded to read_aloud.packs_dir, then this PC's Windows voices (the lists
        are re-read once a minute, so a voice added since shows up; Windows voices need comtypes)."""
        out: list[Voice] = []
        kokoro = cfg.kokoro != "off" and self.kokoro_installed() and self.kokoro.state != "failed"
        if kokoro and self.kokoro_downloaded(cfg.kokoro):
            out += speak.kokoro_voices()
        if cfg.kokoro != "off" and self.kokoro_zh.state != "failed" and self.zh_installed():
            out += speak.zh_voices()
        if self.kokoro_installed():   # Piper needs the same espeak-ng and ONNX Runtime
            at, where, cached = self._piper_voices
            if time.monotonic() - at > 60 or where != cfg.packs_dir:
                cached = speak.installed_piper_voices(cfg.packs_dir)
                self._piper_voices = (time.monotonic(), cfg.packs_dir, cached)
            out += cached
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
        if voice.engine == "kokoro-zh":
            return self.kokoro_zh.ready(self.zh_variant(cfg), cfg.device)
        return voice.engine != "kokoro" or self.kokoro.ready(cfg.kokoro, cfg.device)

    def warm(self, cfg: speak.Config) -> None:
        """Load Kokoro now when the chosen voice is one of its own (a click is coming: the pointer is on the speaker
        button, or a reading is copying the selection), so the first sentence does not wait for the load. The same for
        the Mandarin model when a Mandarin voice is the chosen one."""
        if cfg.kokoro != "off" and speak.zh_voice(cfg.voice):
            variant = self.zh_variant(cfg)
            if variant and self.kokoro_zh.state != "loading" and not self.kokoro_zh.ready(variant, cfg.device) \
                    and self.zh_installed():
                try:
                    self.kokoro_zh.load(variant, cfg.device)
                except SpeechError:
                    pass   # the reading reports it
            return
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
        more processors than one run uses); one on the GPU (fast enough), for Piper (fast on the CPU) and for Windows
        voices (instant). The Mandarin model is a Kokoro too."""
        engine = self._engine(voice)
        return 2 if engine is not None and engine.device != "cuda" else 1

    def lookahead_s(self, voice: Voice) -> float:
        """Seconds of speech to prepare ahead of what plays: more on the GPU, where it costs little."""
        engine = self._engine(voice)
        return 60.0 if engine is None or engine.device == "cuda" else 30.0

    def synth(self, text: str, voice: Voice, speed: float, cfg: speak.Config) -> Audio:
        """One piece of speech, its own silence trimmed (trim), so the pauses between pieces are the configured ones."""
        if voice.engine == "kokoro":
            if cfg.kokoro == "off":
                raise SpeechError("Kokoro is off (read_aloud.kokoro)")
            audio = self.kokoro.synth(text, voice, speed, cfg.kokoro, cfg.device)
        elif voice.engine == "kokoro-zh":
            if cfg.kokoro == "off":
                raise SpeechError("Kokoro is off (read_aloud.kokoro)")
            variant = self.zh_variant(cfg)
            if not variant:
                raise SpeechError("the Mandarin voices are not downloaded; Download them under Read aloud on the tray's "
                                  "Features card")
            audio = self.kokoro_zh.synth(text, voice, speed, variant, cfg.device)
        elif voice.engine == "piper":
            audio = self.piper.synth(text, voice, speed, cfg.packs_dir)
        else:
            audio = self.windows.synth(text, voice, speed)
        audio.pcm = trim(audio.pcm)
        audio.seconds = len(audio.pcm) / 2 / SAMPLE_RATE
        return audio

    def model_name(self, voice: Voice, cfg: speak.Config) -> str:
        if voice.engine == "kokoro":
            return "kokoro-82m" + ("" if cfg.kokoro == "fp32" else f"-{cfg.kokoro}")
        if voice.engine == "kokoro-zh":
            variant = self.kokoro_zh.variant or self.zh_variant(cfg)
            return "kokoro-82m-v1.1-zh" + ("" if variant in ("fp32", "") else f"-{variant}")
        if voice.engine == "piper":
            return f"piper {speak.piper_key(voice.id)[0]}"
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
                                          ("device", (self._engine(voice).device or "cpu") if self._engine(voice)
                                           else "cpu"),
                                          ("speed", cfg.speed), ("stopped", stopped)) if v})
        except Exception as e:  # noqa: BLE001 - a usage record must never break reading
            self.log(f"[read] usage record failed: {_short(e)}")

    def unload_if_idle(self, minutes: float) -> None:
        self.kokoro.unload_if_idle(minutes)
        self.kokoro_zh.unload_if_idle(minutes)
        self.piper.unload_if_idle(minutes)

    def health(self) -> dict:
        k, z = self.kokoro, self.kokoro_zh
        return {"engine": k.state, "model": f"kokoro-82m {k.variant}".strip() if k.variant else "",
                "device": k.device or "", "note": k.note, "idle_s": round(time.monotonic() - k.last_used),
                "gpu_installed": k.gpu_available(), "piper": sorted(self.piper.loaded),
                "zh": {"engine": z.state, "model": f"kokoro-82m-v1.1-zh {z.variant}".strip() if z.variant else "",
                       "device": z.device or "", "note": z.note, "idle_s": round(time.monotonic() - z.last_used)}}


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


def _sha256(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def download_zh(profile: dict, report=lambda *a: None) -> str:
    """Fetch the Mandarin voices (config/installer.yaml kokoro_zh) into the Hugging Face cache: the weights
    read_aloud.kokoro names (fp32 when it is off), the tokenizer and every offered voice, from the pinned revision; the
    weights' sha256 is checked. Run by the setup worker in voice typing's environment (`python -m stacklib.dictation
    speak --download-zh`), which has huggingface_hub."""
    cfg = speak.Config.from_profile(profile)
    variant = cfg.kokoro if cfg.kokoro in speak.ZH_FILES else "fp32"
    missing = []
    for name in (*speak.zh_files(variant), "config.json"):
        try:
            zh_file(name)
        except Exception:  # noqa: BLE001 - not cached
            missing.append(name)
    if not missing:
        return f"Kokoro v1.1-zh {variant} and its {len(speak.ZH_VOICES)} voices already downloaded"
    report(f"downloading Kokoro v1.1-zh ({variant}, about {speak.ZH_SIZES_MB.get(variant, 0)} MB) and "
           f"{len(speak.ZH_VOICES)} Mandarin voices into the Hugging Face cache")
    for name in missing:
        path = zh_file(name, download=True)
        want = speak.ZH_SHA256.get(name)
        if want and _sha256(path) != want:
            raise SpeechError(f"{name} of Kokoro v1.1-zh does not match its pinned sha256; Remove the Mandarin voices "
                              "on the tray's Features card and download them again")
    return f"downloaded Kokoro v1.1-zh {variant} and {len(speak.ZH_VOICES)} Mandarin voices"
