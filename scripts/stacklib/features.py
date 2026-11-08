"""Features the installer offers and the tray shows: what each one is, whether it can be left out, what it costs to run
on this PC, and whether it is installed and linked to the stack.

FEATURES is the one list. The installer's first page (scripts/installer.py and `stack.py install --no-gui`), the tray's
Features card and `stack.py features` all read it. Two features are required: the local models and the gateway, which
every other feature talks to. The others are optional; the installer adds them, and running it again adds more.

Status comes from the system itself (the uv tool environments, files under the media folder, the machine profile,
Claude Desktop's and OpenClaw's configs), never from a record of what the installer chose, so it stays true when
something is installed or removed by hand.

Estimates. Figures marked "measured" come from the reference PC (an RTX 3060 12 GB, a Ryzen 5 5500 with 6 cores and 12
threads, 32 GB of DDR4-2133): benchmarks recorded in memory/state.md between 2026-10-25 and 2026-11-07, and the size
of each install on disk on 2026-11-07. The rest are estimates and say so. Memory is in GB of 2**30 bytes, as Windows
and nvidia-smi count it; disk sizes are in GB of 10**9 bytes, as the installer's free-space checks count them.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from . import IS_WINDOWS, which

GIB = 2 ** 30
REFERENCE = "an RTX 3060 12 GB"


@dataclass(frozen=True)
class Feature:
    id: str
    title: str
    short: str                       # in sentences that list several features ("chat model 5.7 GB, ...")
    summary: str                     # what you get, in one or two sentences
    required: bool = False           # always installed; the installer offers no way to leave it out
    services: tuple[str, ...] = ()   # the tray's service rows that belong to it
    needs_media: bool = False        # installs under the media folder (agent_access.allowed_roots)


FEATURES: tuple[Feature, ...] = (
    Feature("models", "Local models (Ollama)", "chat model",
            "Ollama and the chat model every other feature talks to. Prompts and replies stay on this PC.",
            required=True, services=("ollama",)),
    Feature("gateway", "Gateway and agent tools", "gateway",
            "LiteLLM, the one address every app uses, with the privacy rules; the orchestrator, through which agents "
            "hand work to the departments; and the tray app.", required=True, services=("litellm", "orchestrator")),
    Feature("chat", "Chat in the browser (Open WebUI)", "Open WebUI",
            "Chat with the department models at http://127.0.0.1:3000, with documents, the agents' tools and the "
            "image button.", services=("open_webui",)),
    Feature("tracing", "Trace viewer (Phoenix)", "Phoenix",
            "Shows the steps of each request, for debugging. The tray's Usage tab works without it.",
            services=("phoenix",)),
    Feature("images", "Image generation (ComfyUI)", "ComfyUI",
            "ComfyUI with the Z-Image-Turbo model (Apache-2.0) makes pictures for the chat's image button.",
            services=("comfyui",), needs_media=True),
    Feature("voice_typing", "Voice typing (Whisper)", "voice typing",
            "A hotkey and a floating mic button type what you say into any app. Whisper transcribes on this PC.",
            services=("dictation",)),
    Feature("recordings", "Recordings in Claude Desktop (Whisper)", "recordings",
            "Claude Desktop transcribes audio files through a local Whisper server. The audio stays here; Claude gets "
            "only the text.", needs_media=True),
    Feature("openclaw", "OpenClaw", "OpenClaw",
            "An agent app (Node.js), set up to use only this stack's gateway, so its prompts stay on this PC."),
)
BY_ID = {f.id: f for f in FEATURES}
SERVICE_FEATURE = {svc: f.id for f in FEATURES for svc in f.services}
# Services in machines/_defaults.yaml that no feature installs yet, and why (tests/test_features.py checks both).
NOT_INSTALLABLE = {"kokoro": "text to speech: no installer yet (multimodal plan, package M2)"}
# Services that run from the repository's own Python environment, so they are there whatever is installed.
PROJECT_SERVICES = {"orchestrator"}
# Optional features that machines/<HOST>.yaml switches on or off: (section, key, on value, off value). The installer
# writes them (install.save_features) and the tray's Settings tab changes them.
SWITCHES = {
    "chat": ("services", "open_webui", "native", "off"),
    "tracing": ("observability", "phoenix", True, False),
    "images": ("services", "comfyui", "native", "off"),
    "voice_typing": ("services", "dictation", "native", "off"),
}


def switch_on(fid: str, profile: dict) -> bool:
    section, key, on, _off = SWITCHES[fid]
    return (profile.get(section) or {}).get(key) == on


# ---------------------------------------------------------------- this PC

@dataclass(frozen=True)
class Hardware:
    gpu: str = ""
    vram_gb: float = 0.0           # the card's memory
    desktop_vram_gb: float = 0.0   # what Windows and other programs held when the profile was written
    ram_gb: float = 0.0
    threads: int = 1               # logical processors
    smart_app_control: bool = False

    @property
    def gpu_free_gb(self) -> float:
        return max(0.0, self.vram_gb - self.desktop_vram_gb)

    def describe(self) -> str:
        if self.vram_gb > 0:
            gpu = (f"{self.gpu or 'GPU'} with {self.vram_gb:.1f} GB of GPU memory ({self.desktop_vram_gb:.1f} GB in "
                   "use by Windows and other programs)")
        else:
            gpu = "no NVIDIA GPU found"
        ram = f"{self.ram_gb:.0f} GB of RAM" if self.ram_gb else "RAM size unknown"
        return f"{gpu}, {ram}, {self.threads} logical processors"


def smart_app_control_on() -> bool:
    """Windows 11 Smart App Control enforcing (not evaluating or off). It blocked Phoenix and some compiled Python
    modules on the reference PC, so the installer says so next to the features it affects."""
    if not IS_WINDOWS:
        return False
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\CI\Policy") as key:
            return winreg.QueryValueEx(key, "VerifiedAndReputablePolicyState")[0] == 1
    except OSError:
        return False


DESKTOP_VRAM_MAX = 2.5   # GB: more than the desktop holds at idle means a model was loaded when doctor measured


def hardware(profile: dict) -> Hardware:
    """This PC as `stack.py doctor` recorded it in the machine profile's `detected:` block. The GPU memory in use then
    counts as the desktop's, up to DESKTOP_VRAM_MAX, in case doctor ran while a model was loaded."""
    d = profile.get("detected") or {}
    vram = float(d.get("vram_mib") or 0) / 1024
    idle = d.get("idle_vram_mib")
    desktop = min(float(idle) / 1024, DESKTOP_VRAM_MAX) if idle is not None else min(1.0, vram)
    return Hardware(gpu=str(d.get("gpu") or ""), vram_gb=vram, desktop_vram_gb=desktop if vram else 0.0,
                    ram_gb=float(d.get("ram_gb") or 0), threads=os.cpu_count() or 1,
                    smart_app_control=smart_app_control_on())


# ---------------------------------------------------------------- estimates

@dataclass(frozen=True)
class Estimate:
    disk_gb: float = 0.0           # downloaded and installed, shared downloads aside
    todo_gb: float | None = None   # what is left to download when part of it is already there
    shared: tuple[tuple[str, float, bool], ...] = ()   # (download, GB, already on disk), counted once for all features
    ram_gb: float = 0.0            # system memory while it runs
    ram_busy_gb: float = 0.0       # more system memory while it works (ComfyUI keeps models after a job)
    vram_gb: float = 0.0           # GPU memory held while loaded
    vram_busy_gb: float = 0.0      # GPU memory while it works, when more than vram_gb
    cpu_threads: float = 0.0       # logical processors busy while it works
    gpu_short: str = "none"        # GPU work, for a table column
    gpu: str = ""                  # GPU work, in a sentence
    cpu: str = ""                  # CPU load, in a sentence
    held: str = ""                 # when the memory above is in use
    basis: str = "Estimate."
    note: str = ""

    @property
    def disk_total_gb(self) -> float:
        return self.disk_gb + sum(gb for _key, gb, cached in self.shared if not cached)

    @property
    def vram_peak_gb(self) -> float:
        return max(self.vram_gb, self.vram_busy_gb)

    @property
    def ram_peak_gb(self) -> float:
        return self.ram_gb + self.ram_busy_gb


# (model, context): (GPU GB, system-RAM GB, tokens/s while generating), measured on the reference PC with
# `stack.py bench` and Ollama's /api/ps (memory/state.md, 2026-10-25). Ollama reports bytes: 6,166,413,310 bytes for the
# 9B at 32k is 5.7 GB here. The 35B MoE keeps the experts of 28 layers in memory-mapped system RAM.
MEASURED_MODELS = {
    ("qwen3.5:9b", 32768): (5.7, 0.0, 51),
    ("qwen3.5:9b", 16384): (5.5, 0.0, 51),
    ("qwen3.6:35b-a3b-coding", 32768): (8.7, 11.8, 25),
}
KV_GB_PER_32K = {"f16": 4.0, "q8_0": 2.0, "q4_0": 1.0}   # KV cache of a 7-9B model with grouped-query attention
OLLAMA_RAM_GB = 0.5       # estimate: the Ollama server and the runner's host buffers with every layer on the GPU


def chat_model_memory(profile: dict, hw: Hardware, loaded: list[dict] | None = None) -> tuple[float, float, str, int]:
    """(GPU GB, system-RAM GB, basis, tokens/s or 0) of the primary model at its context. Ollama's own figures when
    the model is loaded with that context now; else a measurement of the reference PC; else weights + KV cache."""
    m = profile.get("models") or {}
    model, ctx = m.get("primary") or "", int(m.get("primary_num_ctx") or 0)
    if not model:
        return 0.0, 0.0, "No local chat model in this hardware class.", 0
    for row in loaded or []:
        if row.get("name") == model and int(row.get("context_length") or 0) == ctx and row.get("size"):
            size, vram = int(row["size"]), int(row.get("size_vram") or 0)
            speed = MEASURED_MODELS.get((model, ctx), (0, 0, 0))[2]
            return vram / GIB, (size - vram) / GIB, "GPU memory measured now (the model is loaded).", speed
    if (model, ctx) in MEASURED_MODELS:
        vram, ram, speed = MEASURED_MODELS[(model, ctx)]
        basis = f"Measured on {REFERENCE}."
    else:
        size = float(((profile.get("catalog") or {}).get(model) or {}).get("size_gb") or 0) * 1e9 / GIB
        kv_type = (profile.get("ollama_env") or {}).get("OLLAMA_KV_CACHE_TYPE") or "f16"
        vram = size + KV_GB_PER_32K.get(kv_type, 4.0) * ctx / 32768 + 0.3   # 0.3 GB: compute buffers
        ram, speed, basis = 0.0, 0, "Estimate: download size plus the context's KV cache."
    if hw.vram_gb <= 0:
        return 0.0, vram + ram, basis, 0
    if vram > hw.gpu_free_gb:   # a smaller card than the one measured: Ollama puts the rest in system RAM
        on_gpu = max(0.0, hw.gpu_free_gb - 0.3)
        return on_gpu, ram + vram - on_gpu, basis + " The model does not fit this card, so Ollama splits it.", 0
    return vram, ram, basis, speed


def _keep_text(keep: str) -> str:
    keep = str(keep).strip()
    if keep in ("-1", "-1s", "-1m"):
        return "until Ollama stops"
    units = {"h": "hour", "m": "minute", "s": "second"}
    if keep[:-1].isdigit() and keep[-1:] in units:
        n = int(keep[:-1])
        return f"{n} {units[keep[-1]]}{'s' if n != 1 else ''} after the last request"
    return f"{keep} after the last request"


def models_to_pull(profile: dict) -> list[str]:
    m = profile.get("models") or {}
    return list(dict.fromkeys(x for x in (m.get("fim"), m.get("embed"), m.get("small"), m.get("primary")) if x))


def model_store(profile: dict) -> str:
    return ((profile.get("ollama_env") or {}).get("OLLAMA_MODELS") or profile.get("model_store")
            or str(Path.home() / ".ollama" / "models"))


def manifest_path(store: str, model: str) -> Path:
    """Where Ollama keeps a pulled model's manifest: library models under registry.ollama.ai/library."""
    name, _, tag = model.partition(":")
    parts = name.split("/")
    if len(parts) == 1:
        parts = ["registry.ollama.ai", "library", *parts]
    elif len(parts) == 2:
        parts = ["registry.ollama.ai", *parts]
    return Path(store, "manifests", *parts, tag or "latest")


def missing_models(profile: dict) -> list[str]:
    store = model_store(profile)
    return [m for m in models_to_pull(profile) if not manifest_path(store, m).is_file()]


def _size_gb(profile: dict, models: list[str]) -> float:
    return sum(float(((profile.get("catalog") or {}).get(x) or {}).get("size_gb") or 0) for x in models)


def _whisper_cached(profile: dict, model: str) -> bool:
    try:
        from . import dictation

        return dictation.model_cached(profile, model)
    except Exception:  # noqa: BLE001 - an unreadable cache counts as not downloaded
        return False


def _images_todo_gb(profile: dict) -> float | None:
    """What images still download when ComfyUI is installed but a model file is missing; None otherwise."""
    from . import media

    m = profile.get("media") or {}
    try:
        if not m.get("root") or not media.comfyui_installed(profile):
            return None
        return sum(x.size_gb for x in media.missing_models(profile, m.get("image_workflow") or "z_image_turbo"))
    except (OSError, KeyError):
        return None


def _cpu(threads: float, hw: Hardware) -> str:
    return f"under 1 of {hw.threads}" if threads < 1 else f"about {threads:.0f} of {hw.threads}"


def estimate(fid: str, profile: dict, hw: Hardware, loaded: list[dict] | None = None) -> Estimate:
    m = profile.get("models") or {}
    gpu = hw.vram_gb > 0
    if fid == "models":
        vram, ram, basis, speed = chat_model_memory(profile, hw, loaded)
        pulls = models_to_pull(profile)
        if not gpu:
            work, cpu_n = "none: the model runs on the CPU, a few tokens per second", float(hw.threads)
        elif ram > 0.5:
            work = (f"busy while it answers; {ram:.1f} GB of the model sit in system RAM, so replies are slower than "
                    "with the whole model on the card")
            cpu_n = max(2.0, hw.threads / 2)
        else:
            work = "busy while it answers" + (f", about {speed} tokens per second on {REFERENCE}" if speed else "")
            cpu_n = 1.0
        others = [f"{x} ({float(((profile.get('catalog') or {}).get(x) or {}).get('size_gb') or 0):.1f} GB)"
                  for x in (m.get("embed"), m.get("fim")) if x]
        note = (f"{m.get('primary')} with a {int(m.get('primary_num_ctx') or 0) // 1024}k context." if m.get("primary")
                else "No local chat model in this hardware class.")
        if others:
            note += f" {' and '.join(others)} load only when something uses them (documents, autocomplete)."
        missing = missing_models(profile)
        return Estimate(
            disk_gb=_size_gb(profile, pulls), todo_gb=_size_gb(profile, missing) if missing != pulls else None,
            ram_gb=OLLAMA_RAM_GB + ram, vram_gb=vram, cpu_threads=cpu_n,
            gpu_short="while answering" if gpu else "none (CPU)", gpu=work,
            cpu=f"{_cpu(cpu_n, hw)} logical processors while it answers; none while idle",
            held=(f"loaded when the tray starts, kept "
                  f"{_keep_text((profile.get('ollama_env') or {}).get('OLLAMA_KEEP_ALIVE') or '5m')}"),
            basis=basis + " Ollama's own memory is an estimate.", note=note)
    if fid == "gateway":
        return Estimate(
            disk_gb=0.6, ram_gb=0.5, cpu_threads=0.2, gpu="none: it passes requests on to the models",
            cpu=f"{_cpu(0.2, hw)} logical processors; close to none while idle", held="always, while the tray runs",
            basis="Measured: LiteLLM takes 0.57 GB on disk and 0.3 GB of memory. The orchestrator and the tray "
                  "(about 0.2 GB together) are estimates.")
    if fid == "chat":
        return Estimate(
            disk_gb=1.9, ram_gb=0.7, cpu_threads=0.2,
            gpu="none of its own: each reply also asks the chat model for a title and tags",
            cpu=(f"{_cpu(0.2, hw)} logical processors; the chat box's microphone runs Open WebUI's own small "
                 "Whisper on the CPU, several processors for a few seconds"),
            held="always, while the tray runs it", basis="Measured: 1.9 GB on disk. Memory is an estimate.")
    if fid == "tracing":
        note = ("Smart App Control is on here; it blocked Phoenix on the reference PC, so it may not start."
                if hw.smart_app_control else "")
        return Estimate(disk_gb=0.5, ram_gb=0.4, cpu_threads=0.1, gpu="none",
                        cpu=f"{_cpu(0.1, hw)} logical processors: it stores each request's steps",
                        held="always, while the tray runs it", basis="Measured: 0.54 GB on disk. Memory is an estimate.",
                        note=note)
    if fid == "images":
        return Estimate(
            disk_gb=16.8, todo_gb=_images_todo_gb(profile), ram_gb=1.5, ram_busy_gb=8.0, vram_gb=0.4,
            vram_busy_gb=10.5, cpu_threads=1.0,
            gpu_short="~11 s per image" if gpu else "not practical",
            gpu=("the whole card for about 11 s per 1024 x 1024 image, 32 s for the first while the model loads"
                 if gpu else "none: without an NVIDIA GPU an image takes many minutes"),
            cpu=f"{_cpu(1.0, hw)} logical processors while it makes an image",
            held=("ComfyUI runs all the time; the image model stays in memory after a job until Chat on the tray's "
                  "GPU card frees it"),
            basis=f"Measured on {REFERENCE}: 16.8 GB on disk, 11.6 GB of GPU memory on the card at the peak, 11 s "
                  "per image. System memory is an estimate.")
    if fid == "voice_typing":
        d = profile.get("dictation") or {}
        model = str(d.get("model") or "large-v3-turbo")
        idle = float(d.get("unload_after_min") or 0)
        return Estimate(
            disk_gb=0.3, shared=((f"whisper:{model}", 1.6, _whisper_cached(profile, model)),), ram_gb=0.4,
            vram_gb=1.2 if gpu else 0.0, cpu_threads=1.0 if gpu else float(hw.threads),
            gpu_short="~0.6 s per phrase" if gpu else "none (CPU)",
            gpu=("a moment per phrase: 15 s of speech in 0.6 s" if gpu
                 else "none: on the CPU the small model takes about 10 s per 15 s of speech"),
            cpu=(f"{_cpu(1.0, hw)} logical processors while you speak; close to none while it waits for the hotkey"
                 if gpu else f"all {hw.threads} logical processors while it transcribes"),
            held="Whisper loads on first use (5-8 s)" + (f" and is freed after {idle:.0f} idle minutes" if idle else ""),
            basis=f"Measured on {REFERENCE}: 1.2 GB of GPU memory, 0.3-0.6 s per phrase. Memory is an estimate.",
            note="Polish mode also asks the chat model to tidy the text, about 1 s per recording.")
    if fid == "recordings":
        model = str((profile.get("media") or {}).get("whisper_model") or "large-v3-turbo")
        return Estimate(
            disk_gb=2.4, shared=((f"whisper:{model}", 1.6, _whisper_cached(profile, model)),), ram_gb=0.5,
            vram_gb=1.1 if gpu else 0.0, cpu_threads=1.0 if gpu else float(hw.threads),
            gpu_short="~4 s per 2 min of audio" if gpu else "none (CPU)",
            gpu="a 2-minute recording in about 4 s" if gpu else "none: on the CPU it runs the small model, slowly",
            cpu=f"{_cpu(1.0 if gpu else hw.threads, hw)} logical processors while it transcribes",
            held=("runs while Claude Desktop is open; the model loads for a transcription and is freed after "
                  "10 idle minutes"),
            basis=f"Measured on {REFERENCE}: 2.4 GB on disk, 1.1 GB of GPU memory, 125 s of audio in 3.5 s. Memory "
                  "is an estimate.")
    if fid == "openclaw":
        return Estimate(
            disk_gb=0.5, ram_gb=0.3, cpu_threads=0.3,
            gpu="none of its own: its prompts run on the chat model through the gateway",
            cpu=f"{_cpu(0.3, hw)} logical processors", held="only while you use it (openclaw chat, or its dashboard)",
            basis="Measured: 0.5 GB on disk. Memory is an estimate.",
            note="Needs Node.js 24.22.1+ or 26.12.1+; setup upgrades Node.js with winget if needed (Windows asks "
                 "for admin).")
    raise KeyError(fid)


def estimates(profile: dict, hw: Hardware | None = None, loaded: list[dict] | None = None) -> dict[str, Estimate]:
    hw = hw or hardware(profile)
    return {f.id: estimate(f.id, profile, hw, loaded) for f in FEATURES}


def download_gb(ids, est: dict[str, Estimate], installed=frozenset(), full: bool = False) -> float:
    """What choosing `ids` downloads and installs: features already installed count nothing, a feature that is partly
    there counts what is left (all of it with `full`, for a new folder), and a shared download (the Whisper model)
    counts once."""
    total, seen = 0.0, set()
    for fid in ids:
        if fid in installed:
            continue
        e = est[fid]
        total += e.todo_gb if e.todo_gb is not None and not full else e.disk_gb
        for key, gb, cached in e.shared:
            if not cached and key not in seen:
                seen.add(key)
                total += gb
    return total


def detail_text(e: Estimate) -> str:
    """Everything known about one feature's load, for the installer's detail box and `stack.py features`."""
    parts = [f"GPU: {e.gpu}." if e.gpu else "", f"CPU: {e.cpu}." if e.cpu else ""]
    mem = []
    if e.vram_peak_gb >= 0.05:
        mem.append(f"{e.vram_gb:.1f} GB of GPU memory" + (f", {e.vram_busy_gb:.1f} GB while it works"
                                                           if e.vram_busy_gb > e.vram_gb else ""))
    if e.ram_gb:
        mem.append(f"{e.ram_gb:.1f} GB of RAM" + (f", up to {e.ram_peak_gb:.1f} GB after a job" if e.ram_busy_gb else ""))
    if mem:
        parts.append(f"Memory: {'; '.join(mem)}.")
    if e.held:
        parts.append(f"When: {e.held}.")
    disk = f"Disk: {e.disk_total_gb:.1f} GB"
    if any(not cached for _k, _gb, cached in e.shared):
        disk += " (the Whisper model is shared with the other Whisper feature)"
    parts.append(disk + ".")
    return " ".join(p for p in (*parts, e.note, e.basis) if p)


def _range(lo: float, hi: float) -> str:
    """"5.7", "0.4 to 10.5" (held, and while working), or "-" for none."""
    if hi < 0.05:
        return "-"
    return f"{lo:.1f} to {hi:.1f}" if hi - lo >= 0.05 and lo >= 0.05 else f"{hi:.1f}"


def cells(e: Estimate, hw: Hardware) -> dict[str, str]:
    """The installer's table columns for one feature."""
    return {"disk": f"{e.disk_total_gb:.1f}", "vram": _range(e.vram_gb, e.vram_peak_gb),
            "ram": _range(e.ram_gb, e.ram_peak_gb), "gpu": e.gpu_short,
            "cpu": _cpu(e.cpu_threads, hw).replace("about ", "~")}


def brief(e: Estimate) -> str:
    """One line for the tray's Features card: GPU memory, RAM, disk, and what keeps the GPU busy."""
    parts = [f"GPU {_range(e.vram_gb, e.vram_peak_gb)} GB"] if e.vram_peak_gb >= 0.05 else []
    parts += [f"RAM {_range(e.ram_gb, e.ram_peak_gb)} GB", f"disk {e.disk_total_gb:.1f} GB"]
    if e.gpu_short != "none":
        parts.append(e.gpu_short)
    return "  ·  ".join(parts)


# ---------------------------------------------------------------- does it fit this PC?

@dataclass(frozen=True)
class Finding:
    level: str   # "ok" | "warn" | "bad"
    text: str


def assess(chosen, est: dict[str, Estimate], hw: Hardware, installed=frozenset()) -> list[Finding]:
    """What the chosen features (the required ones always included) take together on this PC, and what to expect when
    they do not fit: the installer shows these under its table and updates them on every tick."""
    ids = [f.id for f in FEATURES if f.required or f.id in set(chosen)]
    out: list[Finding] = []
    disk = download_gb(ids, est, installed)
    kept = [BY_ID[i].short for i in ids if i in installed and not BY_ID[i].required]
    already = f"{', '.join(kept)} {'is' if len(kept) == 1 else 'are'} installed already." if kept else ""
    if disk >= 0.05:
        out.append(Finding("ok", f"Downloads and installs about {disk:.1f} GB." + (f" {already}" if already else "")))
    else:
        out.append(Finding("ok", "Nothing new to download." + (f" {already[0].upper()}{already[1:]}" if already else "")))
    if hw.vram_gb <= 0:
        out.append(Finding("bad", "No NVIDIA GPU was found, so every model runs on the CPU: replies take many times "
                                  "longer, and images are not practical."))
    else:
        free = hw.gpu_free_gb
        held = [(BY_ID[i].short, est[i].vram_gb) for i in ids if est[i].vram_gb >= 0.05]
        total = sum(gb for _n, gb in held)
        parts = ", ".join(f"{n} {gb:.1f}" for n, gb in held)
        if total <= free:
            out.append(Finding("ok", f"GPU memory with everything loaded at once: about {total:.1f} of the {free:.1f} "
                                     f"GB free ({parts})."))
        else:
            out.append(Finding("warn", f"GPU memory with everything loaded at once: about {total:.1f} GB ({parts}), "
                                       f"more than the {free:.1f} GB free. Ollama then keeps part of the chat model in "
                                       "system RAM, and replies get several times slower."))
        if "images" in ids:
            need = est["images"].vram_busy_gb
            left = free - (total - est["images"].vram_gb)
            if need > free:
                out.append(Finding("warn", f"An image needs about {need:.1f} GB of GPU memory, more than the card has "
                                           f"free ({free:.1f} GB): ComfyUI keeps part of the model in system RAM, so "
                                           "each image takes several times longer."))
            elif need > left:
                out.append(Finding("warn", f"An image needs about {need:.1f} GB of GPU memory while it is made; next "
                                           f"to the other models {max(0.0, left):.1f} GB are left, so ComfyUI moves "
                                           "parts to system RAM and is slower. Click Media on the tray's GPU card "
                                           "before a batch of images, and Chat afterwards."))
            else:
                out.append(Finding("ok", f"An image needs about {need:.1f} GB of GPU memory while it is made; that "
                                         "fits next to the other models."))
    idle = sum(est[i].ram_gb for i in ids)
    busy = idle + sum(est[i].ram_busy_gb for i in ids)
    text = f"System memory for the stack: about {idle:.1f} GB" + (f", up to {busy:.1f} GB after an image job"
                                                                  if busy > idle else "")
    if hw.ram_gb:
        text += f", of the {hw.ram_gb:.0f} GB in this PC."
        if busy > hw.ram_gb / 2:
            out.append(Finding("warn", text + " That leaves little for other programs: close some before heavy "
                                              "jobs, or leave a feature out."))
        else:
            out.append(Finding("ok", text + " Your other programs need the rest."))
    else:
        out.append(Finding("ok", text + "."))
    busiest = max(est[i].cpu_threads for i in ids)
    if hw.vram_gb > 0 and busiest <= 2:
        out.append(Finding("ok", f"CPU: close to idle between requests; about 1 of {hw.threads} logical processors "
                                 "while a model works on the GPU."))
    else:
        out.append(Finding("warn", f"CPU: models that do not fit the GPU use up to {busiest:.0f} of {hw.threads} logical "
                                   "processors while they work, so the PC is slow for other things meanwhile."))
    if hw.smart_app_control and "tracing" in ids and "tracing" not in installed:
        out.append(Finding("warn", "Smart App Control is on: it blocked Phoenix on the reference PC. Leave the trace "
                                   "viewer out unless you need it."))
    return out


# ---------------------------------------------------------------- status

NOT_CHECKED = "Not checked"


@dataclass(frozen=True)
class Status:
    installed: bool
    on: bool             # turned on in the machine profile, or linked to the stack (Claude Desktop, OpenClaw)
    state: str           # a few words for a row
    detail: str = ""     # one sentence: where it is, or what to do
    level: str = "ok"    # ok | warn | bad | off: the tray's dot colour

    @property
    def locked(self) -> bool:
        """Installed and on: the installer keeps it, and Settings in the tray turns it off."""
        return self.installed and self.on

    @property
    def unknown(self) -> bool:
        """The check failed: whether it is installed is not known, so nothing may change it."""
        return self.state == NOT_CHECKED


def _switch(installed: bool, on: bool, what: str, where: str, setting: str) -> Status:
    """Status of a feature that the machine profile turns on or off (a service, or Phoenix tracing)."""
    if installed and on:
        return Status(True, True, "Installed", where)
    if installed:
        return Status(True, False, "Installed, off", f"Turned off in the tray's Settings ({setting}). Turn it on there, "
                                                     "or tick it in the installer.", "off")
    if on:
        return Status(False, True, "Not installed", f"{what} is turned on but not installed: run the installer again.",
                      "warn")
    return Status(False, False, "Not installed", "Not chosen. Run the installer again to add it.", "off")


def _tool_env(env_name: str) -> Path | None:
    """A uv tool's environment, None when it is not installed. Raises when uv cannot say where its tools are: the
    feature then reads "Not checked", not "Not installed", since its program may still start from the launcher. The
    failure is not cached, so the next check (the tray's, a minute later) asks uv again."""
    from . import services

    root = services._uv_tool_dir()
    if root is None:
        services._uv_tool_dir_cache.clear()
        raise RuntimeError("uv did not say where its tools are (`uv tool dir`), so this was not checked")
    return root / env_name if (root / env_name / "pyvenv.cfg").exists() else None


def _status_models(profile: dict, **_) -> Status:
    if not which("ollama"):
        return Status(False, True, "Not installed", "Ollama is not installed: run the installer, which can install it "
                                                    "with winget.", "bad")
    missing = missing_models(profile)
    if missing:
        return Status(False, True, "Models missing", f"{', '.join(missing)} not downloaded yet: run the installer "
                                                     "again, or `uv run scripts/stack.py pull`.", "warn")
    return Status(True, True, "Installed", f"{', '.join(models_to_pull(profile))} in {model_store(profile)}.")


def _status_gateway(profile: dict, **_) -> Status:
    env = _tool_env("litellm")
    if not env:
        return Status(False, True, "Not installed", "LiteLLM is missing: run the installer again.", "bad")
    return Status(True, True, "Installed", f"LiteLLM in {env}; the orchestrator and the tray run from the project's "
                                           "own Python environment.")


def _status_chat(profile: dict, **_) -> Status:
    port = (profile.get("ports") or {}).get("open_webui", 3000)
    return _switch(bool(_tool_env("open-webui")), switch_on("chat", profile), "Open WebUI",
                   f"Open WebUI at http://127.0.0.1:{port}, talking to the gateway.", "Open WebUI (chat)")


def _status_tracing(profile: dict, **_) -> Status:
    port = (profile.get("ports") or {}).get("phoenix", 6006)
    return _switch(bool(_tool_env("arize-phoenix")), switch_on("tracing", profile), "Phoenix",
                   f"Phoenix at http://127.0.0.1:{port}, fed by the gateway.", "Phoenix tracing")


def _status_images(profile: dict, **_) -> Status:
    from . import media

    on = switch_on("images", profile)
    if not (profile.get("media") or {}).get("root"):
        return _switch(False, on, "ComfyUI", "", "ComfyUI (images)")
    if media.comfyui_installed(profile):
        missing = media.missing_models(profile, (profile.get("media") or {}).get("image_workflow") or "z_image_turbo")
        if missing:
            return Status(False, on, "Model missing", f"ComfyUI is installed, but {', '.join(x.name for x in missing)} "
                                                      "is not: run the installer again.", "warn")
        return _switch(True, on, "ComfyUI", f"ComfyUI and Z-Image-Turbo in {media.comfyui_dir(profile)}.",
                       "ComfyUI (images)")
    return _switch(False, on, "ComfyUI", "", "ComfyUI (images)")


def _status_voice_typing(profile: dict, **_) -> Status:
    from . import dictation

    return _switch(dictation.installed(profile), switch_on("voice_typing", profile), "Voice typing",
                   f"Press {dictation.hotkey_label(profile)} or click the mic button; Whisper runs from "
                   f"{dictation.env_dir(profile)}.", "Voice typing")


def desktop_entry() -> dict | None:
    """Claude Desktop's local-whisper entry, None when it has none (or its config cannot be read)."""
    from . import whisper

    try:   # utf-8-sig: an editor may have saved the file with a byte order mark
        data = json.loads(whisper.desktop_config_path().read_text(encoding="utf-8-sig") or "{}")
    except (OSError, ValueError, KeyError):
        return None
    entry = (data.get("mcpServers") or {}).get(whisper.SERVER_NAME) if isinstance(data, dict) else None
    return entry if isinstance(entry, dict) else None


def recordings_installed(profile: dict) -> bool:
    from . import whisper

    return bool((profile.get("media") or {}).get("root")) and whisper.whisper_python(profile).exists() \
        and (whisper.whisper_dir(profile) / "whisper_mcp.py").exists()


def _status_recordings(profile: dict, **_) -> Status:
    entry, installed = desktop_entry(), recordings_installed(profile)
    if installed and entry:
        return Status(True, True, "Linked", "Claude Desktop starts the Whisper server when it opens; restart Claude "
                                            "Desktop after changes.")
    if installed:
        return Status(True, False, "Not in Claude Desktop", "Installed, but Claude Desktop does not list the server. "
                                                            "Tick it in the installer, or run "
                                                            "`uv run scripts/stack.py whisper register`.", "off")
    if entry:
        return Status(False, True, "Files missing", "Claude Desktop lists the Whisper server, but its files are not "
                                                    "in the media folder: run the installer again.", "warn")
    return Status(False, False, "Not installed", "Not chosen. Run the installer again to add it.", "off")


def _status_openclaw(profile: dict, openclaw=None, **_) -> Status:
    from . import clients

    s = openclaw or clients.openclaw((profile.get("ports") or {}).get("litellm", 4000))
    if not which("openclaw"):
        return Status(False, False, "Not installed", "Not chosen. Run the installer again to add it.", "off")
    if s.level == "ok":
        return Status(True, True, "Gateway only", s.detail)
    return Status(True, False, s.state, s.detail, s.level)


_STATUS = {"models": _status_models, "gateway": _status_gateway, "chat": _status_chat, "tracing": _status_tracing,
           "images": _status_images, "voice_typing": _status_voice_typing, "recordings": _status_recordings,
           "openclaw": _status_openclaw}


def statuses(profile: dict, openclaw=None) -> dict[str, Status]:
    """Each feature's status, read from the system. `openclaw` passes a clients.openclaw() result the caller already
    has. A check that fails reads "Not checked" with the reason, so one bad config file cannot hide the rest; such a
    feature keeps the profile's switch as `on`, and nothing changes it (see locked)."""
    out = {}
    for f in FEATURES:
        try:
            out[f.id] = _STATUS[f.id](profile, openclaw=openclaw)
        except Exception as e:  # noqa: BLE001 - shown on the row
            on = f.required or (f.id in SWITCHES and switch_on(f.id, profile))
            out[f.id] = Status(False, on, NOT_CHECKED, str(e) or type(e).__name__, "warn")
    return out


def not_installed(status: dict[str, Status]) -> list[str]:
    """Features that are not (fully) installed, in catalog order; a failed check counts as unknown, not missing."""
    return [f.id for f in FEATURES if f.id in status and not status[f.id].installed and not status[f.id].unknown]


def service_installed(svc: str, status: dict[str, Status]) -> bool | None:
    """Whether a service's program is installed; None when unknown (no status yet, or a service no feature installs).
    A feature that only lacks a model ("Models missing", "Model missing") still has its program, and the orchestrator
    runs from the repository's own environment."""
    if svc in PROJECT_SERVICES:
        return True
    fid = SERVICE_FEATURE.get(svc)
    if fid is None or fid not in status or status[fid].unknown:
        return None
    return status[fid].state != "Not installed"


# ---------------------------------------------------------------- the installer's choice

RECOMMENDED = {
    "chat": lambda hw: True,
    "tracing": lambda hw: not hw.smart_app_control,   # Smart App Control blocked Phoenix on the reference PC
    "images": lambda hw: hw.vram_gb >= 10,            # Z-Image-Turbo int8 peaks at 10.5 GB; smaller cards offload
    "voice_typing": lambda hw: False,                 # holds a hotkey and 1.2 GB of GPU memory: only when asked for
    "recordings": lambda hw: False,                   # changes Claude Desktop's config: only when asked for
    "openclaw": lambda hw: True,
}


def locked(fid: str, status: dict[str, Status]) -> bool:
    """Ticked and greyed out in the installer: required, installed and on, or on in the profile while its check
    failed (the installer cannot tell what is there, so it leaves the switch as it is)."""
    s = status.get(fid)
    return BY_ID[fid].required or bool(s and (s.locked or (s.unknown and s.on)))


def initial_choice(status: dict[str, Status], hw: Hardware) -> dict[str, bool]:
    """What the installer ticks first:
    - required, installed-and-on, and unknown-but-on features: ticked and locked;
    - a feature the profile turns on whose program or model is missing: ticked, so setup repairs it;
    - a feature that is installed but off stays off, except OpenClaw that bypasses the gateway (the installer offers
      the fix);
    - the rest follow the recommendation for this PC."""
    out = {}
    for f in FEATURES:
        s = status.get(f.id)
        if locked(f.id, status) or (s and s.on and not s.unknown):
            out[f.id] = True
        elif s and (s.installed or s.unknown):
            out[f.id] = f.id == "openclaw" and s.installed
        else:
            out[f.id] = RECOMMENDED.get(f.id, lambda hw: False)(hw)
    return out
