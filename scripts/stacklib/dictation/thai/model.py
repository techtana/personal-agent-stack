# Adapted from kunato/wayu-kokoro-thai-v1 (Hugging Face), revision abf63dc118365bea784fa881bdd1dce4b2cc1fd4:
# kokoro_thai/onnx_infer.py, licensed under the Apache License, Version 2.0
# (http://www.apache.org/licenses/LICENSE-2.0), as the repository states. Changes: the sessions are opened by read
# aloud's engine (tts.KokoroTh, on the GPU or the CPU); token ids come in, not text; the loader, the precision switch
# and the token counter are left out.
"""The Thai Kokoro model's three ONNX graphs and the host-side steps between them. numpy only.

    prosody   input_ids, style_dur, speed            -> pred_dur, d, t_en
    (host)    repeat each token's columns by its duration (KModel.forward's alignment matrix, as the gather it is)
    curves    en, style_dur                          -> f0_curve, n_curve
    (host)    harmonic source + STFT, in float64     -> har
    decoder   asr, f0_curve, n_curve, style_acou, har -> audio at 24 kHz

The harmonic source runs on the host because its phase accumulates to ~1.4e5 radians over a piece, where float32's
spacing (~8e-3) would be an audible error; in float64 it is exact. Its noise comes from numpy seeded per piece, so the
same text and voice always sound the same.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

GRAPHS = ("prosody", "curves", "decoder")
# SineGen / iSTFTNet constants (asserted against the checkpoint at upstream's export)
HARMONICS = 9              # 8 overtones + the fundamental
UPSAMPLE_SCALE = 300       # prod(upsample_rates) * gen_istft_hop_size
SAMPLES_PER_FRAME = 600    # audio samples per predicted duration unit, 24 kHz
SAMPLE_RATE = 24000
VOICED_THRESHOLD = 10.0
SINE_AMP = 0.1
NOISE_STD = 0.003
N_FFT = 20
HOP = 5
DEFAULT_SEED = 1234


@dataclass
class Graphs:
    """The three sessions and the harmonic source's weights (onnx/source_params.npz)."""
    prosody: Any
    curves: Any
    decoder: Any
    source_weight: np.ndarray   # SourceModuleHnNSF.l_linear, applied on the host
    source_bias: np.ndarray
    window: np.ndarray          # the STFT's analysis window

    def get_providers(self) -> list[str]:
        """The execution providers all three sessions use (CUDA only when every graph runs on it)."""
        first, *rest = (s.get_providers() for s in (self.prosody, self.curves, self.decoder))
        return [p for p in first if all(p in r for r in rest)]


def styles(data) -> dict[int, np.ndarray]:
    """onnx/styles.npz (opened with numpy.load) as speaker number -> its (1, 256) style vector."""
    return {int(k): np.asarray(data[k], dtype=np.float32).reshape(1, 256) for k in data.files}


def synth_ids(model: Graphs, ids: list[int], ref_s: np.ndarray, speed: float = 1.0,
              seed: int = DEFAULT_SEED) -> np.ndarray:
    """Token ids (at most about 510) and a speaker's style vector -> 24 kHz float32 audio."""
    if not ids:
        return np.zeros(0, dtype=np.float32)
    ref_s = np.asarray(ref_s, dtype=np.float32).reshape(1, 256)
    style_dur, style_acou = ref_s[:, 128:], ref_s[:, :128]
    pred_dur, d, t_en = model.prosody.run(None, {
        "input_ids": np.array([[0, *ids, 0]], dtype=np.int64),
        "style_dur": style_dur,
        "speed": np.array([speed], dtype=np.float32),
    })
    index = np.repeat(np.arange(pred_dur.shape[0], dtype=np.int64), pred_dur)
    en = np.ascontiguousarray(d.transpose(0, 2, 1)[:, :, index])
    asr = np.ascontiguousarray(t_en[:, :, index])
    f0_curve, n_curve = model.curves.run(None, {"en": en, "style_dur": style_dur})
    har = harmonic_source(model, f0_curve, seed)
    audio, = model.decoder.run(None, {"asr": asr, "f0_curve": f0_curve, "n_curve": n_curve,
                                      "style_acou": style_acou, "har": har})
    return np.asarray(audio, dtype=np.float32).reshape(-1)


def harmonic_source(model: Graphs, f0_curve: np.ndarray, seed: int) -> np.ndarray:
    """SineGen + SourceModuleHnNSF + the analysis STFT (kokoro.istftnet), phase in float64, noise from `seed`."""
    rng = np.random.default_rng(seed)
    f0 = np.repeat(np.asarray(f0_curve, dtype=np.float64), UPSAMPLE_SCALE, axis=1)[..., None]
    n_samples = f0.shape[1]

    rad = f0 * np.arange(1, HARMONICS + 1, dtype=np.float64) / SAMPLE_RATE
    rad -= np.floor(rad)                       # SineGen's `% 1`
    rand_ini = rng.random((1, HARMONICS))
    rand_ini[:, 0] = 0.0                       # the fundamental keeps its phase
    rad[:, 0, :] += rand_ini

    # phase accumulates at the F0 rate (down, cumulate, back up), or a long piece's sine drifts out of tune
    phase = np.cumsum(_resample(rad, 1 / UPSAMPLE_SCALE), axis=1) * 2 * np.pi
    phase = _resample(phase * UPSAMPLE_SCALE, UPSAMPLE_SCALE)

    voiced = (f0 > VOICED_THRESHOLD).astype(np.float64)
    amplitude = voiced * NOISE_STD + (1 - voiced) * SINE_AMP / 3
    noise = rng.standard_normal((1, n_samples, HARMONICS))
    waves = np.sin(phase) * SINE_AMP * voiced + amplitude * noise

    merged = np.tanh(waves @ model.source_weight.T + model.source_bias)
    return _stft(merged[0, :, 0].astype(np.float32), model.window)


def _resample(x: np.ndarray, scale: float) -> np.ndarray:
    """Linear resampling along axis 1, as torch's F.interpolate(align_corners=False): half-pixel source coordinates,
    clamped to the input at both edges."""
    length = x.shape[1]
    out_length = int(length * scale)
    source = (np.arange(out_length, dtype=np.float64) + 0.5) / scale - 0.5
    np.clip(source, 0, length - 1, out=source)
    lower = np.floor(source).astype(np.int64)
    upper = np.minimum(lower + 1, length - 1)
    weight = (source - lower)[None, :, None]
    return x[:, lower] * (1 - weight) + x[:, upper] * weight


def _stft(audio: np.ndarray, window: np.ndarray) -> np.ndarray:
    """The generator's cat([magnitude, phase]) as torch.stft makes it: centred with reflect padding, one-sided."""
    padded = np.pad(audio, N_FFT // 2, mode="reflect")
    n_frames = (len(padded) - N_FFT) // HOP + 1
    frames = np.lib.stride_tricks.as_strided(
        padded, (n_frames, N_FFT), (padded.strides[0] * HOP, padded.strides[0]))
    spectrum = np.fft.rfft(frames * window, axis=1).T[None]
    return np.concatenate([np.abs(spectrum), np.angle(spectrum)], axis=1).astype(np.float32)
