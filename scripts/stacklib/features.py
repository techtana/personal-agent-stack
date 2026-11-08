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
and nvidia-smi count it; disk sizes are in GB of 10**9 bytes, as the installer's free-space checks count them. The
numbers themselves (model sizes, each program's footprint, the choices offered) live in config/installer.yaml.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from . import IS_WINDOWS, catalog, which

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
    requires: tuple[str, ...] = ()   # features it runs inside; choosing it chooses them too
    offered: bool = True             # False: no longer installed; listed only while on this PC, to remove it


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
    Feature("read_aloud", "Read aloud (Kokoro)", "read aloud",
            "A hotkey and a speaker button read selected text aloud in any app, with natural Kokoro voices on this "
            "PC's CPU, or Windows' own voices. It runs in the voice typing app, so it comes with voice typing.",
            requires=("voice_typing",)),
    # Served only Claude Desktop, which is closed source: the stack keeps no ties to such apps, so it is no longer
    # installed, and the tray and the installer list it only while it is on this PC, to remove it.
    Feature("recordings", "Recordings in Claude Desktop (Whisper)", "recordings",
            "A local Whisper server for Claude Desktop, which is closed source. No longer offered: the stack keeps no "
            "ties to closed-source apps. Remove takes the server, its models and Claude Desktop's entry off this PC.",
            needs_media=True, offered=False),
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
    "read_aloud": ("read_aloud", "enabled", True, False),
}


def with_requirements(chosen) -> set[str]:
    """The chosen features plus the ones they run inside (read aloud needs voice typing's app)."""
    out = set(chosen)
    for fid in list(out):
        if fid in BY_ID:
            out.update(BY_ID[fid].requires)
    return out


def dependents(fid: str) -> list[str]:
    """Features that need `fid`: unticking it unticks them."""
    return [f.id for f in FEATURES if fid in f.requires]


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
    cpu_bursts: bool = False       # runs on the CPU by design, in short bursts (read aloud's Kokoro), not as GPU spill
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
# `stack.py bench` and Ollama's /api/ps (memory/state.md, 2026-10-25; config/installer.yaml models.*.measured). Ollama
# reports bytes: 6,166,413,310 bytes for the 9B at 32k is 5.7 GB here.
MEASURED_MODELS = catalog.measured_models()
# KV cache of a 7-9B model with grouped-query attention, per 32k tokens of context
KV_GB_PER_32K = {str(k): float(v) for k, v in (catalog.ollama().get("kv_gb_per_32k") or {"f16": 4.0}).items()}
OLLAMA_RAM_GB = float(catalog.ollama().get("server_ram_gb") or 0.5)   # estimate: the server and a runner's host buffers


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


def app_model_store() -> str:
    """The Ollama app's own Settings > Model location, "" when none is set. It overrides OLLAMA_MODELS."""
    from . import ollama

    return ollama.app_model_location()


def effective_model_store(profile: dict) -> str:
    """Where Ollama really keeps models: the app's Model location when set, otherwise the profile's folder."""
    return app_model_store() or model_store(profile)


def store_override_note(profile: dict, store: str | None = None) -> str:
    """Why `store` (default: the profile's) is not where Ollama puts models, or "" when it is."""
    app = app_model_store()
    store = store or model_store(profile)
    if not app or not store or Path(app) == Path(store):
        return ""
    return (f"The Ollama app's own Settings > Model location is {app}, which overrides {store}: Ollama keeps its "
            f"models there. Use {app} as the models folder (installer), or change Model location in Ollama's "
            "Settings first.")


_tags_cache: dict[str, tuple[float, set[str] | None]] = {}


def ollama_models(profile: dict) -> set[str] | None:
    """Names the running Ollama reports (/api/tags); None when it does not answer. Kept for 5 s, because one status
    pass asks twice (estimate and status) and a refused localhost connect takes about 2 s on Windows."""
    import time

    from . import ollama

    port = (profile.get("ports") or {}).get("ollama") or 11434
    base = f"http://127.0.0.1:{port}"
    hit = _tags_cache.get(base)
    if hit and time.monotonic() - hit[0] < 5:
        return hit[1]
    names = ollama.model_names(base)
    _tags_cache[base] = (time.monotonic(), names)
    return names


def missing_models(profile: dict) -> list[str]:
    """Models the profile wants that Ollama does not have. Asks the running Ollama first, since only it knows which
    folder it reads; when it is off, looks for the manifests where it will read them (effective_model_store)."""
    have = ollama_models(profile)
    if have is not None:
        return [m for m in models_to_pull(profile) if m not in have]
    store = effective_model_store(profile)
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
    fp = catalog.feature_footprint(fid)
    if fid == "gateway":
        return Estimate(
            disk_gb=fp["disk_gb"], ram_gb=fp["ram_gb"], cpu_threads=0.2, gpu="none: it passes requests on to the models",
            cpu=f"{_cpu(0.2, hw)} logical processors; close to none while idle", held="always, while the tray runs",
            basis="Measured: LiteLLM takes 0.57 GB on disk and 0.3 GB of memory. The orchestrator and the tray "
                  "(about 0.2 GB together) are estimates.")
    if fid == "chat":
        return Estimate(
            disk_gb=fp["disk_gb"], ram_gb=fp["ram_gb"], cpu_threads=0.2,
            gpu="none of its own: each reply also asks the chat model for a title and tags",
            cpu=(f"{_cpu(0.2, hw)} logical processors; the chat box's microphone runs Open WebUI's own small "
                 "Whisper on the CPU, several processors for a few seconds"),
            held="always, while the tray runs it", basis=f"Measured: {fp['disk_gb']:.1f} GB on disk. Memory is an estimate.")
    if fid == "tracing":
        note = ("Smart App Control is on here; it blocked Phoenix on the reference PC, so it may not start."
                if hw.smart_app_control else "")
        return Estimate(disk_gb=fp["disk_gb"], ram_gb=fp["ram_gb"], cpu_threads=0.1, gpu="none",
                        cpu=f"{_cpu(0.1, hw)} logical processors: it stores each request's steps",
                        held="always, while the tray runs it",
                        basis=f"Measured: {fp['disk_gb']:.1f} GB on disk. Memory is an estimate.", note=note)
    if fid == "images":
        m = profile.get("media") or {}
        size, steps = str(m.get("image_size") or "1024x1024"), int(m.get("image_steps") or 8)
        try:
            w, h = (int(x) for x in size.lower().split("x"))
        except ValueError:
            w = h = 1024
        per_image = float(catalog.images().get("seconds_per_image") or 11.0)   # measured at 1024 x 1024, 8 steps
        secs = per_image * (w * h / 1024 ** 2) * (steps / 8)   # scales with both
        exact = (w, h, steps) == (1024, 1024, 8)
        return Estimate(
            disk_gb=fp["disk_gb"], todo_gb=_images_todo_gb(profile), ram_gb=fp["ram_gb"], ram_busy_gb=fp["ram_busy_gb"],
            vram_gb=fp["vram_gb"], vram_busy_gb=fp["vram_busy_gb"], cpu_threads=1.0,
            gpu_short=f"~{secs:.0f} s per image" if gpu else "not practical",
            gpu=(f"the whole card for about {secs:.0f} s per {w} x {h} image at {steps} steps, about 20 s more for "
                 "the first while the model loads" if gpu else "none: without an NVIDIA GPU an image takes many minutes"),
            cpu=f"{_cpu(1.0, hw)} logical processors while it makes an image",
            held=("ComfyUI runs all the time; the image model stays in memory after a job until Chat on the tray's "
                  "GPU card frees it"),
            basis=f"Measured on {REFERENCE}: {fp['disk_gb']:.1f} GB on disk, 11.6 GB of GPU memory on the card at the "
                  f"peak, {per_image:.0f} s per 1024 x 1024 image at 8 steps"
                  + ("" if exact else " (other sizes and steps scaled from that)") + ". System memory is an estimate.")
    if fid in ("voice_typing", "recordings"):
        typing = fid == "voice_typing"
        d = profile.get("dictation") or {}
        model = str((d.get("model") if typing else (profile.get("media") or {}).get("whisper_model")) or "large-v3-turbo")
        size, vram, per15 = WHISPER.get(model, WHISPER["large-v3-turbo"])
        measured = model == "large-v3-turbo"
        if measured and not typing and fp["vram_gb"]:
            vram = fp["vram_gb"]   # the recordings server measured 1.1 GB, voice typing 1.2 GB
        shared = ((f"whisper:{model}", size, _whisper_cached(profile, model)),)
        cpu_n = 1.0 if gpu else float(hw.threads)
        if typing:
            idle = float(d.get("unload_after_min") or 0)
            return Estimate(
                disk_gb=fp["disk_gb"], shared=shared, ram_gb=fp["ram_gb"], vram_gb=vram if gpu else 0.0, cpu_threads=cpu_n,
                gpu_short=f"~{per15:.1f} s per phrase" if gpu else "none (CPU)",
                gpu=(f"a moment per phrase: 15 s of speech in about {per15:.1f} s with {model}" if gpu
                     else "none: on the CPU the small model takes about 10 s per 15 s of speech"),
                cpu=(f"{_cpu(1.0, hw)} logical processors while you speak; close to none while it waits for the "
                     "hotkey" if gpu else f"all {hw.threads} logical processors while it transcribes"),
                held="Whisper loads on first use (5-8 s)" + (f" and is freed after {idle:.0f} idle minutes" if idle else ""),
                basis=(f"Measured on {REFERENCE}: 1.2 GB of GPU memory, 0.3-0.6 s per phrase with large-v3-turbo."
                       if measured else f"Estimate for {model}, scaled from large-v3-turbo measured on {REFERENCE}.")
                      + " Memory is an estimate.",
                note="Polish mode also asks the chat model to tidy the text, about 1 s per recording.")
        two_min = per15 * 8 * 0.75   # a long file runs in larger batches than live phrases
        return Estimate(
            disk_gb=fp["disk_gb"], shared=shared, ram_gb=fp["ram_gb"], vram_gb=vram if gpu else 0.0, cpu_threads=cpu_n,
            gpu_short=f"~{two_min:.0f} s per 2 min of audio" if gpu else "none (CPU)",
            gpu=f"a 2-minute recording in about {two_min:.0f} s" if gpu else "none: on the CPU it runs the small model, slowly",
            cpu=f"{_cpu(cpu_n, hw)} logical processors while it transcribes",
            held=("runs while Claude Desktop is open; the model loads for a transcription and is freed after "
                  "10 idle minutes"),
            basis=(f"Measured on {REFERENCE}: {fp['disk_gb']:.1f} GB on disk, {vram:.1f} GB of GPU memory, 125 s of "
                   "audio in 3.5 s."
                   if measured else f"Estimate for {model}, scaled from large-v3-turbo measured on {REFERENCE}.")
                  + " Memory is an estimate.")
    if fid == "read_aloud":
        variant = str((profile.get("read_aloud") or {}).get("kokoro") or "fp32")
        name, disk, ram = KOKORO.get(variant, KOKORO["fp32"])
        disk += _packs_gb(profile)   # the more voices chosen (Piper), on top of Kokoro
        cached = _kokoro_cached(profile, variant)
        idle = float((profile.get("read_aloud") or {}).get("unload_after_min") or 0)
        if not name:
            return Estimate(disk_gb=0.02, ram_gb=0.05, cpu_threads=0.2, gpu="none", cpu="almost none",
                            held="only while it reads", basis="Windows' own voices (read_aloud.kokoro: off).",
                            note="Windows voices make speech almost at once; they sound flatter than Kokoro's.")
        device = str((profile.get("read_aloud") or {}).get("device") or "auto")
        on_gpu = name == "fp32" and gpu and (device == "gpu" or (device == "auto" and hw.vram_gb > 0))
        if on_gpu:
            return Estimate(
                disk_gb=0.02 + disk + KOKORO_GPU_GB, todo_gb=(0.02 + KOKORO_GPU_GB) if cached else None, ram_gb=0.3,
                vram_gb=1.0, cpu_threads=1.0, gpu_short="~0.3 s per sentence",
                gpu="about 0.3 s per sentence of speech on the GPU (12-20x faster than real time), 1.0 GB held while loaded",
                cpu=f"{_cpu(1.0, hw)} logical processors while it prepares speech",
                held="Kokoro loads on its first reading (about 2 s)" + (f" and is freed after {idle:.0f} idle minutes"
                                                                           if idle else ""),
                basis="Measured on the reference PC's RTX 3060: 1.0 GB of GPU memory, 18.6 s of speech in 0.9 s, with "
                      "onnxruntime-gpu 1.31 (CUDA 13) and cuDNN 9; the GPU libraries add about 0.8 GB on disk.",
                note="Falls back to the CPU when the GPU is full (ComfyUI working) or its libraries are missing.")
        return Estimate(
            disk_gb=0.02 + disk, todo_gb=0.02 if cached else None, ram_gb=ram, cpu_threads=hw.threads / 2,
            cpu_bursts=True,
            gpu_short="none (CPU)", gpu="none: Kokoro runs on the CPU, about 3x faster than real time",
            cpu=f"{_cpu(hw.threads / 2, hw)} logical processors while it prepares speech; none while it waits",
            held="Kokoro loads on its first reading (about 2 s)" + (f" and is freed after {idle:.0f} idle minutes"
                                                                       if idle else ""),
            basis=f"Measured on the reference PC's 6-core Ryzen 5 5500: {ram:.1f} GB of RAM with the {name} weights, "
                  "a short sentence ready in 0.8 s, 17 s of speech in 5 s. Faster or slower CPUs scale it.",
            note="Windows' own voices (any language with a Windows voice installed) work too, at once.")
    if fid == "openclaw":
        return Estimate(
            disk_gb=fp["disk_gb"], ram_gb=fp["ram_gb"], cpu_threads=0.3,
            gpu="none of its own: its prompts run on the chat model through the gateway",
            cpu=f"{_cpu(0.3, hw)} logical processors", held="only while you use it (openclaw chat, or its dashboard)",
            basis=f"Measured: {fp['disk_gb']:.1f} GB on disk. Memory is an estimate.",
            note=f"Needs Node.js {_node_requirement()}; setup upgrades Node.js with winget if needed (Windows asks "
                 "for admin).")
    raise KeyError(fid)


def _node_requirement() -> str:
    from .install import node_requirement

    return node_requirement()


# read_aloud.kokoro: (name, download GB with the voices, RAM GB while loaded and reading), measured on the reference
# PC (2026-11-08: working set after a sentence; config/installer.yaml kokoro.variants). "off" reads with Windows voices.
KOKORO = {**{name: (name, float(v.get("download_gb") or 0), float(v.get("ram_gb") or 0))
             for name, v in (catalog.kokoro().get("variants") or {}).items()},
          "off": ("", 0.0, 0.0)}
# onnxruntime-gpu (0.23 GB) and cuDNN 9 for CUDA 13 (0.58 GB), measured 2026-11-08
KOKORO_GPU_GB = float(catalog.kokoro().get("gpu_libraries_gb") or 0.8)


def _packs_gb(profile: dict) -> float:
    """Download size of the Piper voices read_aloud.packs names."""
    from .dictation.speak import PIPER_VOICES

    chosen = (profile.get("read_aloud") or {}).get("packs") or []
    return sum(float((PIPER_VOICES.get(str(k)) or {}).get("size_mb") or 0) for k in chosen) / 1000


def _kokoro_cached(profile: dict, variant: str) -> bool:
    try:
        from . import dictation

        return dictation.kokoro_cached(profile, variant)
    except Exception:  # noqa: BLE001 - an unreadable cache counts as not downloaded
        return False


# faster-whisper model: (download GB, GPU GB in int8_float16, seconds per 15 s of speech on the reference GPU).
# large-v3-turbo was measured (memory/state.md, open items 22 and 23); the others are scaled from it by model size.
WHISPER = {name: (float(m.get("download_gb") or 0), float(m.get("vram_gb") or 0), float(m.get("s_per_15s") or 0))
           for name, m in catalog.whisper_models().items()}


# ---------------------------------------------------------------- options chosen with a feature

@dataclass(frozen=True)
class Option:
    """One setting the installer asks for next to its feature: a key of machines/<HOST>.yaml and its choices."""
    section: str
    key: str
    label: str
    default: str
    number: bool = False   # stored as an int


def _model_choices(profile: dict) -> list[tuple[str, str]]:
    cat = profile.get("catalog") or {}
    names = [n for n, c in cat.items() if (c or {}).get("role") in ("small", "primary")]
    current = (profile.get("models") or {}).get("primary")
    if current and current not in names:
        names.append(current)
    return [(n, f"{n} ({float((cat.get(n) or {}).get('size_gb') or 0):.1f} GB)") for n in names]


def _whisper_choices(_profile: dict) -> list[tuple[str, str]]:
    return [(m, f"{m} ({WHISPER[m][0]:.1f} GB)") for m in WHISPER]


def _hotkey_choices(_profile: dict) -> list[tuple[str, str]]:
    from .dictation.hotkey import CHOICES

    return [(h, "+".join(p.capitalize() for p in h.split("+"))) for h in CHOICES]


def _kokoro_choices(_profile: dict) -> list[tuple[str, str]]:
    fp32, int8 = KOKORO.get("fp32", ("", 0.35, 0))[1], KOKORO.get("int8", ("", 0.12, 0))[1]
    return [("fp32", f"Kokoro ({fp32:.2f} GB)"), ("int8", f"Kokoro, smaller ({int8:.2f} GB)"), ("off", "Windows voices only")]


def _device_choices(_profile: dict) -> list[tuple[str, str]]:
    extra = f"adds {KOKORO_GPU_GB:.1f} GB"
    return [("auto", f"GPU on an NVIDIA PC ({extra}), else CPU"), ("gpu", f"GPU ({extra})"), ("cpu", "CPU")]


OPTIONS: dict[str, list[tuple[Option, object]]] = {
    "models": [
        (Option("models", "primary", "Chat model", str(catalog.ollama().get("default_chat_model") or "qwen3.5:9b")),
         _model_choices),
        (Option("models", "primary_num_ctx", "Context", "32768", number=True),
         lambda _p: [(str(n), f"{n // 1024}k tokens") for n in catalog.context_choices()]),
    ],
    "images": [
        (Option("media", "image_size", "Image size", "1024x1024"),
         lambda _p: [(str(s), str(s).replace("x", " x ")) for s in catalog.images().get("sizes") or ("1024x1024",)]),
        (Option("media", "image_steps", "Steps", "8", number=True),
         lambda _p: [(str(n), f"{n} steps") for n in catalog.images().get("steps") or (8,)]),
    ],
    "voice_typing": [
        (Option("dictation", "model", "Whisper model", "large-v3-turbo"), _whisper_choices),
        (Option("dictation", "hotkey", "Hotkey", "ctrl+alt+d"), _hotkey_choices),
    ],
    "read_aloud": [
        (Option("read_aloud", "kokoro", "Voices", "fp32"), _kokoro_choices),
        (Option("read_aloud", "device", "Runs on", "auto"), _device_choices),
    ],
}


def option_choices(opt_and_fn, profile: dict) -> list[tuple[str, str]]:
    return opt_and_fn[1](profile)


def current_options(profile: dict) -> dict[tuple[str, str], str]:
    """Each option's value in the profile now (the installer's first choice)."""
    out = {}
    for opts in OPTIONS.values():
        for opt, _fn in opts:
            value = (profile.get(opt.section) or {}).get(opt.key)
            out[(opt.section, opt.key)] = str(value) if value not in (None, "") else opt.default
    return out


def option_value(section: str, key: str, value: str):
    """The value as the profile stores it."""
    for opts in OPTIONS.values():
        for opt, _fn in opts:
            if (opt.section, opt.key) == (section, key):
                return int(value) if opt.number else value
    return value


def is_moe(profile: dict, model: str) -> bool:
    """A mixture-of-experts model, whose experts live in mapped RAM (it needs use_mmap on Windows with CUDA)."""
    return "moe" in str(((profile.get("catalog") or {}).get(model) or {}).get("notes") or "").lower()


def with_options(profile: dict, values: dict[tuple[str, str], str]) -> dict:
    """The profile as it will be once the chosen options are written: for estimates on the installer's page."""
    out = {**profile}
    for (section, key), value in values.items():
        out[section] = {**(out.get(section) or {}), key: option_value(section, key, value)}
    return out


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
    busiest = max([est[i].cpu_threads for i in ids if not est[i].cpu_bursts] or [0.0])
    if hw.vram_gb > 0 and busiest <= 2:
        out.append(Finding("ok", f"CPU: close to idle between requests; about 1 of {hw.threads} logical processors "
                                 "while a model works on the GPU."))
    else:
        out.append(Finding("warn", f"CPU: models that do not fit the GPU use up to {busiest:.0f} of {hw.threads} logical "
                                   "processors while they work, so the PC is slow for other things meanwhile."))
    for i in ids:
        if est[i].cpu_bursts:
            out.append(Finding("ok", f"CPU: {BY_ID[i].short} uses about {est[i].cpu_threads:.0f} of {hw.threads} "
                                     "logical processors for a moment per sentence, about a third of the time it "
                                     "speaks."))
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
                                                     "tick it in the installer, or Remove it.", "off")
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
    note = store_override_note(profile)
    if missing:
        return Status(False, True, "Models missing", f"{', '.join(missing)} not downloaded yet: run the installer "
                                                     "again, or `uv run scripts/stack.py pull`." + (f" {note}" if note else ""),
                      "warn")
    if note:
        return Status(True, True, "Installed", f"{', '.join(models_to_pull(profile))} in "
                                               f"{effective_model_store(profile)}. {note}", "warn")
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
                   f"Open WebUI at http://127.0.0.1:{port}, talking to the gateway.", "Chat in the browser")


def _status_tracing(profile: dict, **_) -> Status:
    port = (profile.get("ports") or {}).get("phoenix", 6006)
    return _switch(bool(_tool_env("arize-phoenix")), switch_on("tracing", profile), "Phoenix",
                   f"Phoenix at http://127.0.0.1:{port}, fed by the gateway.", "Trace viewer")


def _status_images(profile: dict, **_) -> Status:
    from . import media

    on = switch_on("images", profile)
    if not (profile.get("media") or {}).get("root"):
        return _switch(False, on, "ComfyUI", "", "Image generation")
    if media.comfyui_installed(profile):
        missing = media.missing_models(profile, (profile.get("media") or {}).get("image_workflow") or "z_image_turbo")
        if missing:
            return Status(False, on, "Model missing", f"ComfyUI is installed, but {', '.join(x.name for x in missing)} "
                                                      "is not: run the installer again.", "warn")
        return _switch(True, on, "ComfyUI", f"ComfyUI and Z-Image-Turbo in {media.comfyui_dir(profile)}.",
                       "Image generation")
    return _switch(False, on, "ComfyUI", "", "Image generation")


def _status_read_aloud(profile: dict, **_) -> Status:
    from . import dictation
    from .dictation.hotkey import label

    from .dictation.speak import PIPER_VOICES, language_label

    key = (profile.get("read_aloud") or {}).get("hotkey") or "ctrl+alt+s"
    more = [language_label(str(PIPER_VOICES[k].get("language") or "")) for k in dictation.installed_packs(profile)]
    extra = f" More voices: {', '.join(dict.fromkeys(more))}." if more else ""
    return _switch(dictation.read_aloud_installed(profile), switch_on("read_aloud", profile), "Read aloud",
                   f"Select text, then press {label(str(key))} or click the speaker button.{extra}", "Read aloud")


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
        return Status(True, True, "Linked", "No longer offered: Claude Desktop is closed source. Remove takes the "
                                            "server, its models and Claude Desktop's entry off this PC.", "warn")
    if installed:
        return Status(True, False, "Not in Claude Desktop", "No longer offered, and Claude Desktop no longer lists "
                                                            "the server: Remove takes its files off this PC.", "off")
    if entry:
        return Status(False, True, "Files missing", "No longer offered: Claude Desktop still lists the Whisper "
                                                    "server, whose files are gone. Remove takes the entry out.", "warn")
    return Status(False, False, "Not installed", "No longer offered: the stack keeps no ties to closed-source apps.",
                  "off")


def _status_openclaw(profile: dict, openclaw=None, **_) -> Status:
    from . import clients

    s = openclaw or clients.openclaw((profile.get("ports") or {}).get("litellm", 4000))
    if not which("openclaw"):
        return Status(False, False, "Not installed", "Not chosen. Run the installer again to add it.", "off")
    if s.level == "ok":
        return Status(True, True, "Gateway only", s.detail)
    return Status(True, False, s.state, s.detail, s.level)


_STATUS = {"models": _status_models, "gateway": _status_gateway, "chat": _status_chat, "tracing": _status_tracing,
           "images": _status_images, "voice_typing": _status_voice_typing, "read_aloud": _status_read_aloud,
           "recordings": _status_recordings,
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


def present(fid: str, status: dict[str, Status]) -> bool:
    """Something of the feature is on this PC (or its check failed): a feature no longer offered is listed only then."""
    s = status.get(fid)
    return bool(s and (s.installed or s.on or s.unknown or s.state in ("Model missing", "Files missing")))


def not_installed(status: dict[str, Status]) -> list[str]:
    """Features that are not (fully) installed, in catalog order; a failed check counts as unknown, not missing."""
    return [f.id for f in FEATURES if f.offered and f.id in status and not status[f.id].installed
            and not status[f.id].unknown]


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
    "read_aloud": lambda hw: False,                   # another hotkey, and Kokoro's 0.35 GB: only when asked for
    "openclaw": lambda hw: True,
}


def locked(fid: str, status: dict[str, Status]) -> bool:
    """Ticked and greyed out in the installer: required, installed and on, or on in the profile while its check
    failed (the installer cannot tell what is there, so it leaves the switch as it is)."""
    s = status.get(fid)
    if not BY_ID[fid].offered:   # never kept by the installer: it can only be removed
        return False
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
        if not f.offered:
            out[f.id] = False
        elif locked(f.id, status) or (s and s.on and not s.unknown):
            out[f.id] = True
        elif s and (s.installed or s.unknown):
            out[f.id] = f.id == "openclaw" and s.installed
        else:
            out[f.id] = RECOMMENDED.get(f.id, lambda hw: False)(hw)
    return out


# ---------------------------------------------------------------- the tray's Kokoro row while read aloud provides it

def read_aloud_row(profile: dict, health: dict | None, status: "Status | None" = None) -> tuple[str, str, str]:
    """(level, state, role) for the tray's Kokoro row while the standalone Kokoro service is off and read aloud runs
    Kokoro inside the voice typing app. level: good | warn | bad | off. health is voice typing's /health answer (None
    while voice typing is down); status is the read_aloud feature's Status, when checked."""
    role = "text to speech: read aloud, inside voice typing"
    if not (profile.get("read_aloud") or {}).get("enabled"):
        if status is not None and not status.installed and not status.unknown:
            return "off", "Not installed", role
        return "off", "Read aloud off", role
    if status is not None and not status.installed and not status.unknown:
        return "warn", "Not installed", role
    read = health.get("read_aloud") if isinstance(health, dict) else None
    if not isinstance(health, dict):
        return "off", "Starts with voice typing", role
    if not isinstance(read, dict) or not read.get("enabled"):
        return "warn", "Restart voice typing", role
    where = {"cuda": "GPU", "cpu": "CPU"}.get(str(read.get("device") or ""), "")
    engine = read.get("engine")
    if engine == "failed":
        return "bad", "Failed (Windows voices read)", role
    if engine == "loading":
        return "warn", "Loading", role
    if read.get("busy"):
        return "good", "Paused" if read.get("paused") else f"Reading{f' ({where})' if where else ''}", role
    if engine == "ready":
        return "good", f"Loaded on the {where}" if where else "Loaded", role
    return "good", "Ready (loads when used)", role
