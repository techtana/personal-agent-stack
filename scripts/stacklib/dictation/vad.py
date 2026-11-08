"""Voice activity detection per 32 ms frame: Silero VAD (the ONNX model faster-whisper ships), streaming.

faster-whisper 1.2's silero_vad_v6.onnx takes [frames, 576] (512 new samples plus the previous 64 as context) and LSTM
state h, c of shape [1, 1, 128]; feeding one frame at a time and carrying h, c is the streaming form of what
faster-whisper does in one batch. It costs well under a millisecond per frame on one CPU thread. When onnxruntime or the
model cannot load, an energy detector with an adaptive noise floor stands in: good enough for a headset or desk
microphone in a quiet room, weaker next to music or a TV.
"""
from __future__ import annotations

import math
import os

import numpy as np

FRAME = 512
CONTEXT = 64


class SileroVad:
    name = "silero"

    def __init__(self) -> None:
        import faster_whisper
        import onnxruntime

        path = os.path.join(os.path.dirname(faster_whisper.__file__), "assets", "silero_vad_v6.onnx")
        opts = onnxruntime.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        opts.log_severity_level = 4
        self.session = onnxruntime.InferenceSession(path, providers=["CPUExecutionProvider"], sess_options=opts)
        names = [i.name for i in self.session.get_inputs()]
        if names != ["input", "h", "c"]:
            raise RuntimeError(f"unexpected Silero model inputs {names}")
        self.reset()

    def reset(self) -> None:
        self.h = np.zeros((1, 1, 128), dtype=np.float32)
        self.c = np.zeros((1, 1, 128), dtype=np.float32)
        self.context = np.zeros(CONTEXT, dtype=np.float32)

    def __call__(self, frame: np.ndarray) -> float:
        x = np.concatenate([self.context, frame]).reshape(1, FRAME + CONTEXT)
        out, self.h, self.c = self.session.run(None, {"input": x, "h": self.h, "c": self.c})
        self.context = frame[-CONTEXT:]
        return float(np.asarray(out).reshape(-1)[0])


class EnergyVad:
    """Speech likelihood from loudness above an adaptive noise floor (fast down, slow up)."""
    name = "energy"

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.floor = -60.0

    def __call__(self, frame: np.ndarray) -> float:
        rms = float(np.sqrt(np.mean(frame * frame))) if frame.size else 0.0
        db = 20 * math.log10(rms + 1e-9)
        if db < self.floor:
            self.floor = db
        else:
            self.floor += (db - self.floor) * 0.003
        self.floor = max(self.floor, -90.0)
        if db < -55:
            return 0.0
        return min(max((db - self.floor - 6.0) / 10.0, 0.0), 1.0)


def make_vad(log=print):
    try:
        return SileroVad()
    except Exception as e:  # noqa: BLE001 - any failure means the fallback
        log(f"[dictation] Silero VAD unavailable ({e}); using the loudness detector")
        return EnergyVad()


def level(frame: np.ndarray) -> float:
    """0..1 loudness for the button's meter (-60 dBFS -> 0, -12 dBFS -> 1)."""
    rms = float(np.sqrt(np.mean(frame * frame))) if frame.size else 0.0
    db = 20 * math.log10(rms + 1e-9)
    return min(max((db + 60.0) / 48.0, 0.0), 1.0)
