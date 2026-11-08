"""Comment-preserving edits of machines/<HOST>.yaml: set one `section.key` and leave every other line as written.

Used by the tray's Settings tab (stacklib/settings.py), the installer and voice typing's quick menu, which must not pull
in the build modules settings.py imports. Multi-line text (voice typing's cleanup prompt) is written as a literal block
(`key: |-` and the lines below it), and a value that already spans several lines is replaced whole.
"""
from __future__ import annotations

import re

import yaml

_WIDTH = 1 << 30  # never fold a long value onto a second line
_SECTION = re.compile(r"^(?P<name>[A-Za-z_][\w-]*):\s*(?P<rest>.*)$")


def dump_scalar(v: object) -> str:
    text = yaml.safe_dump(v, default_flow_style=True, width=_WIDTH, allow_unicode=True).strip()
    return text[:-4].rstrip() if text.endswith("\n...") else text


class _BlockDumper(yaml.SafeDumper):
    """Multi-line strings as literal blocks, readable in the file. When a block cannot hold the text exactly (a space
    before a line break, control characters), PyYAML writes a double-quoted string on one line instead."""


_BlockDumper.add_representer(
    str, lambda d, s: d.represent_scalar("tag:yaml.org,2002:str", s, style="|" if "\n" in s else None))


def _render(key: str, value: object) -> list[str]:
    """`key: value` as unindented lines: one line, or the key line and a literal block for multi-line text."""
    if isinstance(value, str) and "\n" in value:
        text = yaml.dump({key: value}, Dumper=_BlockDumper, allow_unicode=True, width=_WIDTH, sort_keys=False,
                         default_flow_style=False)
        return text.rstrip("\n").split("\n")
    return [f"{key}: {dump_scalar(value)}"]


def _indented(prefix: str, rendered: list[str]) -> list[str]:
    return [prefix + ln if ln else ln for ln in rendered]


def _width(line: str) -> int:
    return len(line) - len(line.lstrip())


def _value_node(root, line: int, column: int):
    """The value node of the mapping key that starts at (line, column), anywhere in the composed document."""
    todo = [root]
    while todo:
        node = todo.pop()
        if isinstance(node, yaml.MappingNode):
            for k, v in node.value:
                if (k.start_mark.line, k.start_mark.column) == (line, column):
                    return v
                todo.append(v)
        elif isinstance(node, yaml.SequenceNode):
            todo.extend(node.value)
    return None


_COMMENT = re.compile(r"\s+#.*$")


def _extent(lines: list[str], i: int, column: int) -> tuple[int, str]:
    """(index of the first line after the value of the key at line i, column `column`; the comment that follows the
    value on line i). Most values end on their key's line; a literal or folded block, or a quoted string continued on
    the next lines, runs further. When the text does not parse, the value is taken to end on line i."""
    after_colon = lines[i].split(":", 1)[1]
    fallback = (i + 1, mt.group(0) if (mt := _COMMENT.search(after_colon)) else "")
    try:
        root = yaml.compose("\n".join(lines))
    except yaml.YAMLError:
        return fallback
    value = _value_node(root, i, column) if root is not None else None
    if value is None:
        return fallback
    start, end = value.start_mark, value.end_mark
    if end.line == i:
        rest = lines[i][end.column:]
        return i + 1, rest if rest.lstrip().startswith("#") else ""
    comment = ""
    if isinstance(value, yaml.ScalarNode) and value.style in ("|", ">") and start.line == i:
        header = re.match(r"[|>][-+0-9]*(\s+#.*)?$", lines[i][start.column:])  # `|-  # note`
        comment = (header.group(1) or "") if header else ""
    # A block ends where the next line starts (column 0 of the mark's line); a quoted string ends inside its last line.
    inside = end.line < len(lines) and lines[end.line][:end.column].strip()
    stop = min(end.line + 1 if inside else end.line, len(lines))
    while stop > i + 1 and not lines[stop - 1].strip():
        stop -= 1  # blank lines after a block separate it from the next key: keep them
    return stop, comment


def set_key(text: str, section: str, key: str, value: object) -> str:
    """Set `section.key` in YAML text, keeping comments and the layout of everything else."""
    lines = text.splitlines()
    rendered = _render(key, value)
    start = next((i for i, ln in enumerate(lines) if (mt := _SECTION.match(ln)) and mt["name"] == section), None)
    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines += [f"{section}:", *_indented("  ", rendered)]
        return "\n".join(lines) + "\n"
    rest = _SECTION.match(lines[start])["rest"].split(" #", 1)[0].strip()
    if rest and rest != "{}" and not rest.startswith("#"):
        # Flow mapping on one line (`cloud: {enabled: auto}`): rewrite that section as a block.
        current = yaml.safe_load(rest) or {}
        lines[start:start + 1] = [f"{section}:", *[ln for k, v in current.items() for ln in _indented("  ", _render(k, v))]]
    elif rest == "{}":
        lines[start] = f"{section}:"
    end = start + 1
    indent = ""
    while end < len(lines) and (not lines[end].strip() or lines[end][0] in " \t#"):
        if not indent and lines[end].strip() and not lines[end].lstrip().startswith("#"):
            indent = lines[end][: _width(lines[end])]  # the section's first key (a block's text is indented deeper)
        end += 1
    indent = indent or "  "
    pat = re.compile(rf"^\s+{re.escape(key)}:(\s|$)")
    for i in range(start + 1, end):
        if pat.match(lines[i]) and _width(lines[i]) == len(indent):
            stop, comment = _extent(lines, i, len(indent))
            new = _indented(indent, rendered)
            if len(new) > 1:
                # Deeper-indented comment lines below the key continue its comment. Under a block's key line they
                # would become part of the text, so they move above the key, together with the comment they continue.
                moved = []
                while stop < len(lines) and lines[stop].lstrip().startswith("#") and _width(lines[stop]) > len(indent):
                    moved.append(indent + lines[stop].strip())
                    stop += 1
                if moved:
                    new = ([indent + comment.strip()] if comment.strip() else []) + moved + new
                    comment = ""
            new[len(new) - len(rendered)] += comment
            lines[i:stop] = new
            return "\n".join(lines) + "\n"
    last = max([i for i in range(start, end) if lines[i].strip() and lines[i][0] != "#"] or [start])
    lines[last + 1:last + 1] = _indented(indent, rendered)
    return "\n".join(lines) + "\n"

