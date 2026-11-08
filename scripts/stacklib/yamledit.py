"""Comment-preserving edits of machines/<HOST>.yaml: set one `section.key` and leave every other line as written.

Used by the tray's Settings tab (stacklib/settings.py), the installer and voice typing's quick menu, which must not pull
in the build modules settings.py imports.
"""
from __future__ import annotations

import re

import yaml


def dump_scalar(v: object) -> str:
    text = yaml.safe_dump(v, default_flow_style=True, width=10_000, allow_unicode=True).strip()
    return text[:-4].rstrip() if text.endswith("\n...") else text


_SECTION = re.compile(r"^(?P<name>[A-Za-z_][\w-]*):\s*(?P<rest>.*)$")


def set_key(text: str, section: str, key: str, value: object) -> str:
    """Set `section.key` in YAML text, keeping comments and the layout of everything else."""
    lines = text.splitlines()
    rendered = dump_scalar(value)
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
        lines[start:start + 1] = [f"{section}:", *[f"  {k}: {dump_scalar(v)}" for k, v in current.items()]]
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
