"""Media services: ComfyUI (images, later video and music) and Kokoro (speech), installed under media.root.

Plan: docs/design/plans/2026-11-01-multimodal-stack.md. Every folder written here comes from the profile's `media:`
section and must pass the path guard (stacklib/paths.py), so nothing lands in a default cache outside the folders the
owner allowed.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from . import IS_WINDOWS, REPO, catalog, info, warn, which
from . import paths

COMFY_DIR = REPO / "config" / "comfyui"
WORKFLOWS_DIR = COMFY_DIR / "workflows"
COMFYUI_GIT = catalog.images()["comfyui_git"]
# Open-licence weights only (decision D-M3). Each row is also listed in config/comfyui/MODELS.md.
OPEN_LICENCES = {str(x).lower() for x in catalog.images().get("open_licences") or ()}


@dataclass(frozen=True)
class Model:
    name: str        # file name ComfyUI sees
    folder: str      # subfolder of ComfyUI's models/ (diffusion_models, text_encoders, vae, ...)
    repo: str        # Hugging Face repository
    path: str        # file path inside the repository
    licence: str
    size_gb: float
    workflow: str    # workflow that needs it

    @property
    def url(self) -> str:
        return f"https://huggingface.co/{self.repo}/resolve/main/{self.path}"


# Every model file a workflow needs, from config/installer.yaml images.workflows.
MODELS = tuple(Model(str(f["file"]), str(f["folder"]), str(f["repo"]), str(f["path"]), str(f["licence"]),
                     float(f["size_gb"]), str(name))
               for name, wf in (catalog.images().get("workflows") or {}).items() for f in wf.get("models") or ())


# ---------------------------------------------------------------- folders

def media(profile: dict) -> dict:
    return profile.get("media") or {}


def comfyui_dir(profile: dict) -> Path:
    return Path(media(profile)["comfyui_dir"])


def comfyui_python(profile: dict) -> Path:
    return comfyui_dir(profile) / ".venv" / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")


def comfyui_installed(profile: dict) -> bool:
    return bool(media(profile).get("root")) and (comfyui_dir(profile) / "main.py").exists() and comfyui_python(profile).exists()


def models_for(workflow: str) -> list[Model]:
    return [m for m in MODELS if m.workflow == workflow]


def missing_models(profile: dict, workflow: str) -> list[Model]:
    root = Path(media(profile)["models_dir"])
    return [m for m in models_for(workflow) if not (root / m.folder / m.name).exists()]


def guarded(profile: dict) -> None:
    """Raise PermissionError when a media folder is outside agent_access.allowed_roots."""
    errors, _ = paths.check(profile)
    if errors:
        raise PermissionError("; ".join(errors))


# ---------------------------------------------------------------- service commands

def service_command(profile: dict, svc: str, base_env: dict) -> dict | None:
    """Command, cwd and env for a media service, or None when it is not installed (start() then reports why)."""
    m = media(profile)
    if not m.get("root"):
        return None
    if svc == "comfyui":
        python = comfyui_python(profile)
        env = {**base_env, "PYTHONUTF8": "1"}
        if m.get("hf_home"):
            env["HF_HOME"] = m["hf_home"]
        return {
            "cmd": [str(python), "main.py",  # not -P: main.py imports from its own folder
                    "--listen", "127.0.0.1", "--port", str(profile["ports"]["comfyui"]),
                    "--output-directory", m["output_dir"], "--input-directory", m["input_dir"],
                    "--disable-auto-launch", *[str(a) for a in m.get("comfyui_args") or []]],
            "cwd": str(comfyui_dir(profile)),
            "env": env,
        }
    if svc == "kokoro":
        kdir = Path(m["root"]) / "kokoro"
        python = kdir / ".venv" / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")
        env = {**base_env, "PYTHONUTF8": "1", "USE_GPU": "false", "USE_ONNX": "false",
               "PYTHONPATH": f"{kdir}{os.pathsep}{kdir / 'api'}", "MODEL_DIR": "src/models", "VOICES_DIR": "src/voices/v1_0",
               "WEB_PLAYER_PATH": str(kdir / "web")}
        if m.get("hf_home"):
            env["HF_HOME"] = m["hf_home"]
        return {
            "cmd": [str(python), "-P", "-m", "uvicorn", "api.src.main:app", "--host", "127.0.0.1",
                    "--port", str(profile["ports"]["kokoro"])],
            "cwd": str(kdir),
            "env": env,
        }
    return None


# ---------------------------------------------------------------- workflows and Open WebUI

def load_workflow(name: str) -> tuple[dict, list[dict]]:
    """(API-format workflow, Open WebUI node map) from config/comfyui/workflows/<name>.json and <name>.nodes.json."""
    wf = json.loads((WORKFLOWS_DIR / f"{name}.json").read_text(encoding="utf-8"))
    nodes = json.loads((WORKFLOWS_DIR / f"{name}.nodes.json").read_text(encoding="utf-8"))
    return wf, nodes


def image_settings(profile: dict) -> dict[str, object]:
    """Open WebUI config keys (persistent config rows) for image generation through ComfyUI; {} when it is off."""
    m = media(profile)
    if profile["services"].get("comfyui") != "native" or not m.get("root"):
        return {}
    wf, nodes = load_workflow(m.get("image_workflow") or "z_image_turbo")
    model = next((n["inputs"]["unet_name"] for n in wf.values() if n.get("class_type") == "UNETLoader"), "")
    return {
        "image_generation.enable": True,
        "image_generation.engine": "comfyui",
        "image_generation.model": model,
        "image_generation.size": str(m.get("image_size") or "1024x1024"),
        "image_generation.steps": int(m.get("image_steps") or 8),
        "image_generation.comfyui.base_url": f"http://127.0.0.1:{profile['ports']['comfyui']}",
        "image_generation.comfyui.workflow": json.dumps(wf, indent=2),
        "image_generation.comfyui.nodes": nodes,
    }


# Display names for the chat's image label; a workflow without one is named after its diffusion model file.
WORKFLOW_LABELS = {name: str(wf["label"]) for name, wf in (catalog.images().get("workflows") or {}).items()
                   if wf.get("label")}


def image_label(profile: dict) -> str:
    """What the gateway appends to the chat reply after Open WebUI made an image, e.g.
    "Z-Image-Turbo int8 (ComfyUI, 1024x1024, 8 steps)"; '' when image generation is off."""
    s = image_settings(profile)
    if not s:
        return ""
    workflow = media(profile).get("image_workflow") or "z_image_turbo"
    name = WORKFLOW_LABELS.get(workflow) or Path(str(s["image_generation.model"])).stem or workflow
    return f"{name} (ComfyUI, {s['image_generation.size']}, {s['image_generation.steps']} steps)"


def openwebui_env(profile: dict) -> dict[str, str]:
    """The same settings as environment variables. Open WebUI reads them only for keys its database does not have
    yet (a fresh install); `provision_openwebui` writes them into an existing database."""
    s = image_settings(profile)
    if not s:
        return {}
    return {
        "ENABLE_IMAGE_GENERATION": "true",
        "IMAGE_GENERATION_ENGINE": "comfyui",
        "IMAGE_GENERATION_MODEL": str(s["image_generation.model"]),
        "IMAGE_SIZE": str(s["image_generation.size"]),
        "IMAGE_STEPS": str(s["image_generation.steps"]),
        "COMFYUI_BASE_URL": str(s["image_generation.comfyui.base_url"]),
        "COMFYUI_WORKFLOW": str(s["image_generation.comfyui.workflow"]),
        "COMFYUI_WORKFLOW_NODES": json.dumps(s["image_generation.comfyui.nodes"]),
    }


def openwebui_db(profile: dict) -> Path:
    return Path(profile["data_dir"]) / "open-webui" / "webui.db"


def provision_openwebui(db: Path, settings: dict[str, object]) -> list[str]:
    """Write Open WebUI config rows (key -> JSON value) into its database, after a dated backup. Returns the keys that
    changed. Open WebUI must be restarted to read them. A database that does not exist yet is left alone: the
    environment seeds a fresh one."""
    if not settings or not db.exists():
        return []
    con = sqlite3.connect(db, timeout=30)
    try:
        have = dict(con.execute("select key, value from config").fetchall())
        todo = {k: json.dumps(v) for k, v in settings.items() if have.get(k) != json.dumps(v)}
        if not todo:
            return []
        backup = db.with_name(f"{db.name}.bak-{time.strftime('%Y%m%d-%H%M%S')}-media")
        shutil.copy2(db, backup)
        now = int(time.time())
        with con:
            con.executemany("insert into config(key, value, updated_at) values(?, ?, ?) "
                            "on conflict(key) do update set value = excluded.value, updated_at = excluded.updated_at",
                            [(k, v, now) for k, v in todo.items()])
        info(f"open-webui: wrote {len(todo)} settings; backup {backup.name}")
        return sorted(todo)
    finally:
        con.close()


# ---------------------------------------------------------------- install

def _run(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> None:
    info("  $ " + " ".join(str(c) for c in cmd))
    r = subprocess.run([str(c) for c in cmd], cwd=cwd, env=env, check=False)
    if r.returncode:
        raise RuntimeError(f"{Path(str(cmd[0])).name} exited with code {r.returncode}")


def _uv_env(profile: dict) -> dict:
    m = media(profile)
    env = {**os.environ, "UV_CACHE_DIR": m["uv_cache"], "UV_LINK_MODE": "hardlink"}
    if m.get("hf_home"):
        env["HF_HOME"] = m["hf_home"]
    return env


def system_python() -> str | None:
    """A python.org interpreter (PSF-signed launchers run under Smart App Control; uv's own builds were refused)."""
    if IS_WINDOWS:
        py = which("py")
        if py:
            out = subprocess.run([py, "-3", "-c", "import sys; print(sys.executable)"], capture_output=True, text=True, check=False).stdout.strip()
            if out and "\\uv\\python\\" not in out.lower():
                return out
    return which("python3") or which("python")


# Smart App Control judges each compiled module (.pyd) by its download reputation. On 2026-11-04 it refused PyAV 19.0.2
# and 16.0.1 (cp314 and cp312) but allowed 17.0.0, the oldest version ComfyUI accepts. Pinned (config/installer.yaml
# images.pins) until a newer one passes.
SAC_PINS = tuple(str(x) for x in catalog.images().get("pins") or ())
# Modules ComfyUI needs at start-up that ship compiled code; importing them is how a refused DLL shows up.
IMPORT_CHECK = ("import av, av.audio.frame, av.video.frame, numpy, PIL.Image, safetensors, tokenizers, yaml, aiohttp, torch; "
                "print(torch.__version__, torch.cuda.is_available())")


def install_comfyui(profile: dict, report=lambda *a: None) -> str:
    """Clone or update ComfyUI at media.comfyui_ref, build its venv with PyTorch, install its requirements."""
    guarded(profile)
    m = media(profile)
    target = comfyui_dir(profile)
    git = which("git")
    if not git:
        from .winget_build import package_id

        raise RuntimeError(f"git is not installed (winget install {package_id('git')})")
    ref = m.get("comfyui_ref") or "master"
    depth = int(catalog.images().get("clone_depth") or 50)
    if not (target / ".git").exists():
        report(f"cloning ComfyUI into {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        _run([git, "clone", "--depth", str(depth), COMFYUI_GIT, target])
    report(f"checking out ComfyUI {ref}")
    _run([git, "fetch", "--depth", str(depth), "origin", ref], cwd=target)
    _run([git, "checkout", "-q", "FETCH_HEAD"], cwd=target)
    commit = subprocess.run([git, "rev-parse", "--short", "HEAD"], cwd=target, capture_output=True, text=True, check=False).stdout.strip()
    uv = which("uv") or "uv"
    env = _uv_env(profile)
    python = comfyui_python(profile)
    if not python.exists():
        base = system_python()
        report("creating ComfyUI's Python environment")
        _run([uv, "venv", *(["--python", base] if base else []), target / ".venv"], env=env)
    have_torch = subprocess.run([python, "-c", "import torch"], capture_output=True, check=False).returncode == 0
    if not have_torch:
        report("installing PyTorch (about 3 GB)")
        torch = [str(x) for x in catalog.images().get("torch") or ("torch", "torchvision", "torchaudio")]
        _run([uv, "pip", "install", "--python", python, *torch,
              "--index-url", m.get("torch_index") or "https://download.pytorch.org/whl/cu130"], env=env)
    report("installing ComfyUI's requirements")
    overrides = Path(m["uv_cache"]) / "comfyui-overrides.txt"
    overrides.parent.mkdir(parents=True, exist_ok=True)
    overrides.write_text("\n".join(SAC_PINS) + "\n", encoding="utf-8")
    _run([uv, "pip", "install", "--python", python, "-r", target / "requirements.txt", "--override", overrides], env=env)
    check = subprocess.run([python, "-c", IMPORT_CHECK], capture_output=True, text=True, check=False)
    if check.returncode:
        tail = (check.stderr or "").strip().splitlines()[-1:] or ["no output"]
        hint = " Smart App Control refused a DLL; see CodeIntegrity event 3033 for the file." if "Application Control" in tail[0] else ""
        raise RuntimeError(f"ComfyUI's environment does not import ({tail[0]}).{hint}")
    return f"ComfyUI {commit} with torch {check.stdout.strip()}"


def download(url: str, dest: Path, report=lambda *a: None) -> None:
    """Stream a file to dest through dest.part, resuming a partial download."""
    part = dest.with_name(dest.name + ".part")
    dest.parent.mkdir(parents=True, exist_ok=True)
    have = part.stat().st_size if part.exists() else 0
    req = urllib.request.Request(url, headers={"Range": f"bytes={have}-"} if have else {})
    with urllib.request.urlopen(req, timeout=60) as r:
        if have and r.status != 206:
            have = 0  # the server ignored the range: start over
        total = have + int(r.headers.get("Content-Length") or 0)
        with open(part, "ab" if have else "wb") as f:
            done, last = have, 0.0
            while chunk := r.read(1 << 20):
                f.write(chunk)
                done += len(chunk)
                if time.monotonic() - last > 1:
                    report(f"{dest.name}: {done / 1e9:.1f} of {total / 1e9:.1f} GB", done / total if total else None)
                    last = time.monotonic()
    os.replace(part, dest)


def install_models(profile: dict, workflow: str, report=lambda *a: None) -> str:
    guarded(profile)
    root = Path(media(profile)["models_dir"])
    todo = missing_models(profile, workflow)
    for m in todo:
        if m.licence.lower() not in OPEN_LICENCES:
            raise RuntimeError(f"{m.name}: licence {m.licence} is not an open licence (decision D-M3)")
    for i, m in enumerate(todo):
        report(f"downloading {m.name} ({m.size_gb:.1f} GB, model {i + 1} of {len(todo)})")
        download(m.url, root / m.folder / m.name, report)
    return f"{len(todo)} model files downloaded" if todo else "models already present"


# ---------------------------------------------------------------- GPU mode (plan section 7, G1)

def _post(url: str, body: dict, timeout: float = 30) -> None:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout):
        pass


def free_comfyui(profile: dict) -> bool:
    """Ask ComfyUI to unload its models and free VRAM. False when it does not answer."""
    try:
        _post(f"http://127.0.0.1:{profile['ports']['comfyui']}/free", {"unload_models": True, "free_memory": True})
        return True
    except (urllib.error.URLError, OSError):
        return False


def unload_model(profile: dict, name: str) -> bool:
    """Unload one model Ollama holds (keep_alive 0); the next request that needs it loads it again. False when Ollama
    did not answer."""
    base = f"http://127.0.0.1:{profile['ports']['ollama']}"
    try:
        _post(f"{base}/api/generate", {"model": name, "keep_alive": 0}, timeout=60)
        return True
    except (urllib.error.URLError, OSError):
        warn(f"could not unload {name}")
        return False


def unload_ollama(profile: dict) -> list[str]:
    """Unload every model Ollama holds (keep_alive 0). Returns their names."""
    base = f"http://127.0.0.1:{profile['ports']['ollama']}"
    try:
        with urllib.request.urlopen(f"{base}/api/ps", timeout=5) as r:
            loaded = [m.get("name") or m.get("model") for m in json.load(r).get("models", [])]
    except (urllib.error.URLError, OSError, ValueError):
        return []
    for name in loaded:
        unload_model(profile, name)
    return loaded


def gpu_mode(profile: dict, mode: str) -> str:
    """'media': free the card for ComfyUI by unloading Ollama's models. 'chat': ask ComfyUI to free its memory; the
    next chat request loads the chat model again."""
    if mode == "media":
        names = unload_ollama(profile)
        return f"unloaded {', '.join(names)} from Ollama" if names else "no Ollama model was loaded"
    if mode == "chat":
        return "ComfyUI freed its memory" if free_comfyui(profile) else "ComfyUI did not answer (nothing to free)"
    raise ValueError(f"unknown GPU mode {mode!r}")
