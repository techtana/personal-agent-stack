"""Find the CUDA 12 cuBLAS DLLs CTranslate2 needs on Windows, without installing the CUDA toolkit.

CTranslate2's Windows wheel ships cuDNN but not cuBLAS. Ollama ships the CUDA 12 runtime (cudart, cuBLAS, cuBLASLt,
signed by NVIDIA) in lib/ollama/cuda_v12, and every machine in this stack has Ollama, so voice typing borrows those
DLLs instead of downloading the 0.5 GB nvidia-cublas-cu12 wheel. Measured on the reference machine (2026-11-07): large-v3-turbo
with int8_float16 on the RTX 3060 transcribed 15 s of speech in 0.6 s with Ollama's copy.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

CUBLAS = "cublas64_12.dll"


def candidate_dirs(prefix: Path | None = None) -> list[Path]:
    """Folders that may hold cublas64_12.dll, most specific first. `prefix` is the environment whose pip-installed
    nvidia-cublas-cu12 counts (default: the running interpreter's)."""
    out: list[Path] = []
    prefix = Path(prefix or sys.prefix)
    out.append(prefix / "Lib" / "site-packages" / "nvidia" / "cublas" / "bin")  # pip nvidia-cublas-cu12
    for key, value in sorted(os.environ.items()):
        if key.upper().startswith("CUDA_PATH") and value:
            out.append(Path(value) / "bin")
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        out.append(Path(local) / "Programs" / "Ollama" / "lib" / "ollama" / "cuda_v12")
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if d:
            out.append(Path(d))
    seen: set[str] = set()
    unique = []
    for d in out:
        key = str(d).lower()
        if key not in seen:
            seen.add(key)
            unique.append(d)
    return unique


def cublas_dirs(prefix: Path | None = None) -> list[Path]:
    return [d for d in candidate_dirs(prefix) if (d / CUBLAS).exists()]


def add_cuda_dlls() -> Path | None:
    """Put the first folder with cuBLAS 12 on the DLL search path (both os.add_dll_directory and PATH: CTranslate2 loads
    cuBLAS lazily with LoadLibrary, which may not use the added directories). Returns that folder, or None."""
    found = cublas_dirs()
    if not found or os.name != "nt":
        return None
    d = found[0]
    try:
        os.add_dll_directory(str(d))
    except OSError:
        pass
    if str(d).lower() not in os.environ.get("PATH", "").lower():
        os.environ["PATH"] = str(d) + os.pathsep + os.environ.get("PATH", "")
    return d


# ---------------------------------------------------------------- read aloud's Kokoro on CUDA 13

def kokoro_cuda_dirs(prefix: Path | None = None) -> list[Path]:
    """Folders onnxruntime-gpu 1.31 needs for Kokoro on the GPU: cuDNN 9 for CUDA 13 (the nvidia-cudnn-cu13 wheel in
    the environment) and the CUDA 13 runtime and cuBLAS that Ollama ships in lib/ollama/cuda_v13 (signed by NVIDIA)."""
    prefix = Path(prefix or sys.prefix)
    out = [prefix / "Lib" / "site-packages" / "nvidia" / "cudnn" / "bin"]
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        out.append(Path(local) / "Programs" / "Ollama" / "lib" / "ollama" / "cuda_v13")
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if d and (Path(d) / "ollama.exe").exists():
            out.append(Path(d) / "lib" / "ollama" / "cuda_v13")
    found = {"cudnn64_9.dll": None, "cudart64_13.dll": None, "cublas64_13.dll": None}
    keep: list[Path] = []
    for d in out:
        for name in found:
            if found[name] is None and (d / name).exists():
                found[name] = d
                if d not in keep:
                    keep.append(d)
    return keep if all(found.values()) else []


def add_kokoro_cuda_dlls(prefix: Path | None = None) -> bool:
    """Put cuDNN 9 and the CUDA 13 runtime on the DLL search path; False when one of them is missing."""
    dirs = kokoro_cuda_dirs(prefix)
    if not dirs or os.name != "nt":
        return False
    for d in dirs:
        try:
            os.add_dll_directory(str(d))
        except OSError:
            pass
        if str(d).lower() not in os.environ.get("PATH", "").lower():
            os.environ["PATH"] = str(d) + os.pathsep + os.environ.get("PATH", "")
    return True
