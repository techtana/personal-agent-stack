"""Copy new or changed skills from the user's skill folders into skills/ (rules in skills/sync.yaml).

A skill is a folder with a SKILL.md. Copies are one way: a skill removed at its source stays in skills/ and is
reported as orphaned, so deleting one is a reviewed git change. Skills whose SKILL.md front matter says
`license: Proprietary` are always skipped.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import yaml

from . import REPO, info, warn

SKILLS_DIR = REPO / "skills"
CONFIG = SKILLS_DIR / "sync.yaml"
INDEX = SKILLS_DIR / "index.json"
SKIP_NAMES = {"__pycache__", ".git", ".DS_Store", "Thumbs.db"}


def _files(root: Path) -> dict[str, str]:
    """Relative path -> sha256 (line endings ignored) for every file under root, skipping hidden and cache entries."""
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if any(part in SKIP_NAMES or part.startswith(".") for part in rel.parts) or not p.is_file():
            continue
        # git may rewrite line endings on checkout, so CRLF and LF copies count as equal
        out[rel.as_posix()] = hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    return out


def _front_matter(skill_md: Path) -> dict:
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        return {}
    try:
        return yaml.safe_load(text.split("---", 2)[1]) or {}
    except yaml.YAMLError:
        return {}


def discover(cfg: dict) -> tuple[dict[str, tuple[Path, str]], list[str]]:
    """Return ({name: (folder, origin)}, skipped notes) for every skill the config allows."""
    found: dict[str, tuple[Path, str]] = {}
    skipped: list[str] = []
    exclude = set(cfg.get("exclude") or [])
    synced_ok = set(cfg.get("synced_sources") or [])

    def consider(folder: Path, origin: str) -> None:
        name = folder.name
        if name in exclude:
            skipped.append(f"{name} (excluded in sync.yaml)")
        elif "proprietary" in str(_front_matter(folder / "SKILL.md").get("license", "")).lower():
            skipped.append(f"{name} (proprietary licence)")
        elif name in found:
            skipped.append(f"{name} (duplicate; kept {found[name][1]})")
        else:
            found[name] = (folder, origin)

    for src in cfg.get("sources") or []:
        base = Path(src).expanduser()
        if not base.is_dir():
            warn(f"skills-sync: source {base} not found")
            continue
        for folder in sorted(p for p in base.iterdir() if p.is_dir()):
            if folder.name == "synced":
                for manifest in sorted(folder.glob("*/manifest.json")):
                    for s in json.loads(manifest.read_text(encoding="utf-8")).get("skills", []):
                        d = manifest.parent / s["name"]
                        if not (d / "SKILL.md").exists():
                            continue
                        if s.get("source") in synced_ok:
                            consider(d, f"claude.ai ({s.get('source')})")
                        else:
                            skipped.append(f"{s['name']} (claude.ai source {s.get('source')!r})")
            elif (folder / "SKILL.md").exists():
                consider(folder, src)
    return found, skipped


def sync(dry_run: bool = False) -> dict[str, list[str]]:
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
    found, skipped = discover(cfg)
    index = json.loads(INDEX.read_text(encoding="utf-8")) if INDEX.exists() else {}
    report: dict[str, list[str]] = {"added": [], "updated": [], "unchanged": [], "orphaned": [], "skipped": skipped}

    for name, (src, origin) in sorted(found.items()):
        dest = SKILLS_DIR / name
        src_files = _files(src)
        if dest.exists() and _files(dest) == src_files:
            report["unchanged"].append(name)
            continue
        report["updated" if dest.exists() else "added"].append(name)
        if not dry_run:
            if dest.exists():
                shutil.rmtree(dest)
            for rel in src_files:
                (dest / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src / rel, dest / rel)
            index[name] = {"origin": origin}

    report["orphaned"] = sorted(n for n in index if n not in found and (SKILLS_DIR / n).exists())
    if not dry_run and (report["added"] or report["updated"]):
        INDEX.write_text(json.dumps(dict(sorted(index.items())), indent=2) + "\n", encoding="utf-8")

    for key in ("added", "updated", "unchanged", "orphaned", "skipped"):
        if report[key]:
            info(f"{key:9} {', '.join(report[key])}")
    if dry_run:
        info("(dry run: nothing copied)")
    return report
