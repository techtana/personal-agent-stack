"""Editable machine settings for the tray's Settings tab.

Each setting maps to one key under a top-level section of machines/<HOST>.yaml. Saving patches only those lines, so the
owner's comments and every other key stay as written; the result is re-parsed and must read back the new values before
it replaces the file. Applying then rebuilds the generated configs and restarts what the change affects.
"""
from __future__ import annotations

import re
import urllib.error
from dataclasses import dataclass, field

import yaml

from . import agents_build, litellm_build, ollama, services, winget_build
from . import profile as prof

CTX_CHOICES = ["8192", "16384", "32768", "65536"]


@dataclass
class Setting:
    section: str          # top-level key in the machine file
    key: str
    label: str
    kind: str             # "model" | "choice" | "bool"
    help: str
    effect: str           # "gateway" | "phoenix" | "open_webui" | "ollama"
    choices: list[str] = field(default_factory=list)
    # bool settings store these values for on / off
    on_off: tuple = (True, False)


SETTINGS = [
    Setting("models", "primary", "Primary model", "model",
            "Answers local-primary and every <department>-local alias.", "gateway"),
    Setting("models", "primary_num_ctx", "Primary context (tokens)", "choice",
            "Larger contexts use more VRAM; 32k fits the 9B fully on a 12 GB GPU.", "gateway", CTX_CHOICES),
    Setting("models", "primary_options", "Memory-map primary weights", "bool",
            "Needed for MoE models whose experts live in RAM (the 35B); leave off for dense models.", "gateway",
            on_off=({"use_mmap": True}, {})),
    Setting("models", "small", "Small model", "model", "Answers local-small (cheap tier and housekeeping).", "gateway"),
    Setting("models", "small_num_ctx", "Small context (tokens)", "choice",
            "Keep equal to the primary context when both use the same model, or Ollama reloads between tiers.",
            "gateway", CTX_CHOICES),
    Setting("observability", "jsonl_traces", "Write usage traces", "bool",
            "The gateway logs each request to traces/litellm/; the Usage tab and retros read them.", "gateway"),
    Setting("observability", "phoenix", "Phoenix tracing", "bool",
            "Runs Phoenix and sends gateway spans to it. Smart App Control currently blocks Phoenix here.", "phoenix"),
    Setting("services", "open_webui", "Open WebUI (chat)", "bool",
            "Run the chat UI at http://127.0.0.1:3000.", "open_webui", on_off=("native", "off")),
    Setting("ollama_env", "OLLAMA_KEEP_ALIVE", "Keep models loaded for", "choice",
            "How long Ollama keeps an idle model in memory.", "ollama", ["5m", "30m", "1h", "4h", "-1"]),
    Setting("ollama_env", "OLLAMA_KV_CACHE_TYPE", "KV cache precision", "choice",
            "q8_0 halves cache VRAM versus f16 with little quality loss; q4_0 saves more.", "ollama",
            ["f16", "q8_0", "q4_0"]),
    Setting("ollama_env", "OLLAMA_FLASH_ATTENTION", "Flash attention", "bool",
            "Required for a quantised KV cache.", "ollama", on_off=("1", "0")),
    Setting("ollama_env", "OLLAMA_NUM_PARALLEL", "Parallel requests per model", "choice",
            "Each extra slot multiplies the KV cache.", "ollama", ["1", "2", "4"]),
]

EFFECT_TEXT = {
    "gateway": "rebuild configs, restart LiteLLM",
    "phoenix": "rebuild configs, start or stop Phoenix, restart LiteLLM",
    "open_webui": "start or stop Open WebUI",
    "ollama": "update Ollama's environment and restart Ollama (interrupts running requests)",
}


def setting_id(s: Setting) -> str:
    return f"{s.section}.{s.key}"


def current_values(profile: dict) -> dict[str, object]:
    """Effective value of every setting (machine file merged over defaults), in the form the UI edits."""
    m = profile["models"]
    raw = {
        "models": m,
        "observability": profile["observability"],
        "services": profile["services"],
        "ollama_env": profile["ollama_env"],
    }
    out: dict[str, object] = {}
    for s in SETTINGS:
        v = raw[s.section].get(s.key)
        if s.kind == "bool":
            if s.key == "primary_options":
                out[setting_id(s)] = bool((v or {}).get("use_mmap"))
            else:
                out[setting_id(s)] = v == s.on_off[0] or v is True
        else:
            out[setting_id(s)] = "" if v is None else str(v)
    return out


def installed_models(profile: dict) -> list[str]:
    """Chat-capable models pulled into Ollama (embedding and FIM-base models left out)."""
    try:
        tags = ollama.api(f"http://127.0.0.1:{profile['ports']['ollama']}", "/api/tags", timeout=5).get("models", [])
    except (urllib.error.URLError, OSError, ValueError):
        return []
    names = [t.get("name", "") for t in tags]
    return sorted(n for n in names if n and "embed" not in n and not n.endswith("-base"))


def _to_file_value(s: Setting, ui_value: object) -> object:
    if s.kind == "bool":
        return s.on_off[0] if ui_value else s.on_off[1]
    if s.section == "models" and s.key.endswith("num_ctx"):
        return int(ui_value)
    return str(ui_value)


def _dump_scalar(v: object) -> str:
    text = yaml.safe_dump(v, default_flow_style=True, width=10_000, allow_unicode=True).strip()
    return text[:-4].rstrip() if text.endswith("\n...") else text


_SECTION = re.compile(r"^(?P<name>[A-Za-z_][\w-]*):\s*(?P<rest>.*)$")


def set_key(text: str, section: str, key: str, value: object) -> str:
    """Set `section.key` in YAML text, keeping comments and the layout of everything else."""
    lines = text.splitlines()
    rendered = _dump_scalar(value)
    start = next((i for i, ln in enumerate(lines) if (mt := _SECTION.match(ln)) and mt["name"] == section), None)
    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines += [f"{section}:", f"  {key}: {rendered}"]
        return "\n".join(lines) + "\n"
    rest = _SECTION.match(lines[start])["rest"].split(" #", 1)[0].strip()
    if rest and rest != "{}" and not rest.startswith("#"):
        # Flow mapping on one line (`cloud: {enabled: auto}`): rewrite that section as a block.
        current = yaml.safe_load(rest) or {}
        lines[start:start + 1] = [f"{section}:", *[f"  {k}: {_dump_scalar(v)}" for k, v in current.items()]]
    elif rest == "{}":
        lines[start] = f"{section}:"
    end = start + 1
    indent = "  "
    while end < len(lines) and (not lines[end].strip() or lines[end][0] in " \t#"):
        if lines[end].strip() and not lines[end].lstrip().startswith("#") and indent == "  ":
            indent = lines[end][: len(lines[end]) - len(lines[end].lstrip())]
        end += 1
    pat = re.compile(rf"^(?P<lead>\s+{re.escape(key)}:)(?P<val>[^#]*?)(?P<comment>\s+#.*)?$")
    for i in range(start + 1, end):
        mt = pat.match(lines[i])
        if mt and len(lines[i]) - len(lines[i].lstrip()) == len(indent):
            lines[i] = f"{mt['lead']} {rendered}{mt['comment'] or ''}"
            return "\n".join(lines) + "\n"
    last = max([i for i in range(start, end) if lines[i].strip() and lines[i][0] != "#"] or [start])
    lines.insert(last + 1, f"{indent}{key}: {rendered}")
    return "\n".join(lines) + "\n"


def changed(profile: dict, edits: dict[str, object]) -> list[Setting]:
    cur = current_values(profile)
    return [s for s in SETTINGS if setting_id(s) in edits and edits[setting_id(s)] != cur[setting_id(s)]]


def save(profile: dict, edits: dict[str, object]) -> list[Setting]:
    """Write the edited settings into machines/<HOST>.yaml. Returns the settings that changed."""
    todo = changed(profile, edits)
    if not todo:
        return []
    path = prof.machine_file(profile["name"])
    text = path.read_text(encoding="utf-8")
    for s in todo:
        text = set_key(text, s.section, s.key, _to_file_value(s, edits[setting_id(s)]))
    parsed = yaml.safe_load(text)
    for s in todo:
        want = _to_file_value(s, edits[setting_id(s)])
        if (parsed.get(s.section) or {}).get(s.key) != want:
            raise ValueError(f"could not write {setting_id(s)} safely; edit {path.name} by hand")
    path.write_text(text, encoding="utf-8", newline="\n")
    return todo


def rebuild(profile: dict) -> None:
    """Same generators as `stack.py build`."""
    agents_build.build_all(profile)
    litellm_build.build(profile)
    winget_build.build()


def apply(old_profile: dict, edits: dict[str, object], log=print) -> dict:
    """Save, rebuild and restart what the change needs. Returns the new resolved profile."""
    todo = save(old_profile, edits)
    profile = prof.resolve_profile(old_profile["name"])
    effects = {s.effect for s in todo}
    if not effects:
        log("No changes.")
        return profile
    log(f"Saved {len(todo)} setting(s) to machines/{profile['name']}.yaml")
    supervised = services._task_managed()
    if effects & {"gateway", "phoenix"}:
        rebuild(profile)
        log("Rebuilt gateway and agent configs")
    if "ollama" in effects:
        ollama.set_user_env(profile["ollama_env"])
        log("Restarting Ollama...")
        ollama.restart(f"http://127.0.0.1:{profile['ports']['ollama']}")
    if "phoenix" in effects:
        if profile["observability"].get("phoenix"):
            services.start(profile, ["phoenix"])
        else:
            services.stop(old_profile, ["phoenix"])
    if "open_webui" in effects:
        if profile["services"].get("open_webui") == "native":
            services.start(profile, ["open_webui"])
        else:
            services.stop(old_profile, ["open_webui"])
    if effects & {"gateway", "phoenix"}:
        owned = next(r for r in services.status(profile) if r["service"] == "litellm")
        if "litellm" in supervised:
            log("LiteLLM runs under a scheduled task: restart it with `stack.py tasks stop litellm` then `start`")
        elif owned["healthy"] and not owned["pid"]:
            log("LiteLLM was started outside this stack, so it was not restarted; restart it to load the new config")
        else:
            log("Restarting LiteLLM...")
            services.stop(profile, ["litellm"])
            services.start(profile, ["litellm"])
            ok = services.wait_healthy(profile, ["litellm"], timeout=120)["litellm"]
            log("LiteLLM is back" if ok else "LiteLLM did not come back within 2 minutes; see .run/logs/litellm.log")
    return profile
