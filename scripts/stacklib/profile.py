"""Machine profiles: detection, hardware-class selection, resolution."""
from __future__ import annotations

import json
import os
import platform
import re
import socket
import subprocess
from datetime import date
from pathlib import Path

import yaml

from . import IS_WINDOWS, MACHINES_DIR, REPO, warn

DEFAULTS_FILE = MACHINES_DIR / "_defaults.yaml"
POLICY_FILE = REPO / "policy" / "privacy.yaml"


def machine_name() -> str:
    return os.environ.get("AGENT_STACK_MACHINE") or os.environ.get("COMPUTERNAME") or socket.gethostname().split(".")[0]


def load_defaults() -> dict:
    return yaml.safe_load(DEFAULTS_FILE.read_text(encoding="utf-8"))


def load_policy() -> dict:
    """policy/privacy.yaml; a missing file means everything private and external models off."""
    doc = yaml.safe_load(POLICY_FILE.read_text(encoding="utf-8")) if POLICY_FILE.exists() else {}
    doc = doc or {}
    doc.setdefault("location", "onprem")
    ext = doc.setdefault("external", {})
    ext.setdefault("enabled", False)
    ext.setdefault("providers", {})
    return doc


def machine_file(name: str | None = None) -> Path:
    return MACHINES_DIR / f"{name or machine_name()}.yaml"


def load_machine(name: str | None = None) -> dict:
    p = machine_file(name)
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def _run(cmd: list[str], timeout: int = 20) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def detect_hardware() -> dict:
    """Best-effort hardware facts. Never raises; missing values are None."""
    d: dict = {"os": platform.system().lower(), "detected_at": date.today().isoformat()}
    smi = _run(["nvidia-smi", "--query-gpu=name,memory.total,memory.used,driver_version", "--format=csv,noheader,nounits"])
    if smi.strip():
        name, total, used, drv = [x.strip() for x in smi.strip().splitlines()[0].split(",")[:4]]
        d.update(gpu=name, vram_mib=int(float(total)), idle_vram_mib=int(float(used)), gpu_driver=drv)
    else:
        d.update(gpu=None, vram_mib=0, idle_vram_mib=None, gpu_driver=None)
    if IS_WINDOWS:
        ps = (
            "$cs=Get-CimInstance Win32_ComputerSystem; $cpu=Get-CimInstance Win32_Processor | Select-Object -First 1; "
            "$mods=Get-CimInstance Win32_PhysicalMemory | ForEach-Object { '{0} GB @ {1} MT/s' -f [math]::Round($_.Capacity/1GB), $_.ConfiguredClockSpeed }; "
            "$disks=Get-PSDrive -PSProvider FileSystem | Where-Object {$_.Free -ne $null} | ForEach-Object { @{ $_.Name = [math]::Round($_.Free/1GB) } }; "
            "@{ ram_gb=[math]::Round($cs.TotalPhysicalMemory/1GB,1); cpu=('{0} ({1}C/{2}T)' -f $cpu.Name.Trim(), $cpu.NumberOfCores, $cs.NumberOfLogicalProcessors); "
            "ram_modules=($mods -join ', '); disk_free_gb=$disks } | ConvertTo-Json -Compress -Depth 3"
        )
        out = _run(["powershell", "-NoProfile", "-Command", ps], timeout=40)
        try:
            j = json.loads(out)
            disks = {}
            for item in j.get("disk_free_gb") or []:
                disks.update(item)
            d.update(ram_gb=j.get("ram_gb"), cpu=j.get("cpu"), ram_modules=j.get("ram_modules"), disk_free_gb=disks)
        except (json.JSONDecodeError, AttributeError):
            warn("PowerShell hardware query failed; RAM/CPU unknown")
    else:
        try:
            mem = Path("/proc/meminfo").read_text()
            kb = int(re.search(r"MemTotal:\s+(\d+)", mem).group(1))
            d["ram_gb"] = round(kb / 1024 / 1024, 1)
        except (OSError, AttributeError):
            d["ram_gb"] = None
        d["cpu"] = platform.processor() or _run(["sh", "-c", "lscpu | grep 'Model name' | cut -d: -f2"]).strip() or None
        d["ram_modules"] = None
        d["disk_free_gb"] = {}
    return d


def pick_class(defaults: dict, detected: dict) -> str:
    vram = detected.get("vram_mib") or 0
    ram = detected.get("ram_gb") or 0
    for cls in defaults["hardware_classes"]:
        w = cls.get("when") or {}
        if vram >= w.get("vram_mib_min", 0) and ram >= w.get("ram_gb_min", 0):
            return cls["name"]
    return defaults["hardware_classes"][-1]["name"]


def write_profile(name: str | None = None, refresh: bool = False) -> Path:
    """Create machines/<name>.yaml from detection, or refresh only its `detected:` block."""
    name = name or machine_name()
    p = machine_file(name)
    defaults = load_defaults()
    existing = load_machine(name) if p.exists() else {}
    if existing and not refresh:
        return p
    detected = detect_hardware()
    doc = existing or {
        "name": name,
        "os": "windows" if IS_WINDOWS else detected["os"],
        "hardware_class": pick_class(defaults, detected),
        "model_store": "",
        "data_dir": ".run",
        "models": {},
        "ollama_env": {},
        "cloud": {"enabled": "auto"},
        "notes": [],
    }
    doc["detected"] = detected
    if not existing:
        doc["hardware_class"] = pick_class(defaults, detected)
    header = (
        f"# Machine profile for {name}. Re-detect with: uv run scripts/stack.py doctor --write-profile --refresh\n"
        "# `detected:` is overwritten by --refresh; everything else is yours.\n"
    )
    p.write_text(header + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return p


def resolve_profile(name: str | None = None) -> dict:
    """Merge defaults + machine file + environment into one flat profile dict used by every generator."""
    defaults = load_defaults()
    m = load_machine(name)
    if not m:
        raise FileNotFoundError(f"no machine profile at {machine_file(name)}; run: uv run scripts/stack.py doctor --write-profile")
    cls_name = m.get("hardware_class") or pick_class(defaults, m.get("detected", {}))
    cls = next((c for c in defaults["hardware_classes"] if c["name"] == cls_name), defaults["hardware_classes"][-1])
    models = dict(cls["models"])
    models["primary_num_ctx"] = cls["primary_num_ctx"]
    models["small_num_ctx"] = cls["small_num_ctx"]
    # Extra Ollama request options per role (e.g. use_mmap), forwarded by LiteLLM into Ollama's `options`.
    models["primary_options"] = dict(cls.get("primary_options") or {})
    models["reviewer_options"] = dict(cls.get("reviewer_options") or {})
    models.update({k: v for k, v in (m.get("models") or {}).items() if v is not None})
    ollama_env = dict(defaults["ollama_env"])
    ollama_env.update(m.get("ollama_env") or {})
    if m.get("model_store"):
        ollama_env.setdefault("OLLAMA_MODELS", m["model_store"])
    auto = {"OLLAMA_MAX_LOADED_MODELS": str(cls["max_loaded_models"]), "OLLAMA_CONTEXT_LENGTH": str(max(models["primary_num_ctx"], 4096))}
    for k, v in list(ollama_env.items()):
        if v == "{auto}":
            ollama_env[k] = auto.get(k, "")
    data_dir = Path(m.get("data_dir") or ".run")
    if not data_dir.is_absolute():
        data_dir = REPO / data_dir
    return {
        "name": m.get("name") or machine_name(),
        "os": m.get("os") or ("windows" if IS_WINDOWS else "linux"),
        "hardware_class": cls_name,
        "detected": m.get("detected", {}),
        "models": models,
        "policy": load_policy(),
        "ollama_env": ollama_env,
        "ports": {**defaults["ports"], **(m.get("ports") or {})},
        "services": {**defaults["services"], **(m.get("services") or {})},
        "observability": {**defaults["observability"], **(m.get("observability") or {})},
        "claude_code": {**defaults["claude_code"], **(m.get("claude_code") or {})},
        "model_store": m.get("model_store") or "",
        "data_dir": data_dir,
        "catalog": defaults.get("model_catalog", {}),
    }
