"""WCAG 2.x contrast ratio for foreground/background color pairs (rule A11Y-01).

Usage:
    python contrast.py "#767676" "#ffffff"
    python contrast.py "rgba(0,0,0,.5)" white "#999" "#222"   # several pairs: fg bg fg bg ...
    python contrast.py --fix "#aaaaaa" "#ffffff"                # also suggest the nearest passing foreground

Accepts #rgb, #rgba, #rrggbb, #rrggbbaa, rgb()/rgba(), CSS basic color names and Tk grayNN/greyNN.
A translucent foreground is blended over its background first. Standard library only.
"""

from __future__ import annotations

import argparse
import re
import sys

NAMED = {
    "black": (0, 0, 0), "white": (255, 255, 255), "gray": (128, 128, 128), "grey": (128, 128, 128),
    "silver": (192, 192, 192), "red": (255, 0, 0), "maroon": (128, 0, 0), "orange": (255, 165, 0),
    "yellow": (255, 255, 0), "olive": (128, 128, 0), "lime": (0, 255, 0), "green": (0, 128, 0),
    "aqua": (0, 255, 255), "cyan": (0, 255, 255), "teal": (0, 128, 128), "blue": (0, 0, 255),
    "navy": (0, 0, 128), "fuchsia": (255, 0, 255), "magenta": (255, 0, 255), "purple": (128, 0, 128),
    "lightgray": (211, 211, 211), "lightgrey": (211, 211, 211), "darkgray": (169, 169, 169),
    "darkgrey": (169, 169, 169), "dimgray": (105, 105, 105), "dimgrey": (105, 105, 105),
    "gainsboro": (220, 220, 220), "whitesmoke": (245, 245, 245),
}

# (label, minimum ratio) per WCAG 2.2 success criterion.
THRESHOLDS = [
    ("AA text", 4.5),          # SC 1.4.3
    ("AA large text", 3.0),    # SC 1.4.3, >= 24 px, or >= 18.66 px bold
    ("AA UI/graphics", 3.0),   # SC 1.4.11 non-text contrast
    ("AAA text", 7.0),         # SC 1.4.6
    ("AAA large text", 4.5),   # SC 1.4.6
]


def parse_color(text: str) -> tuple[float, float, float, float]:
    """Return (r, g, b, alpha) with r, g, b in 0-255 and alpha in 0-1."""
    s = text.strip().lower()
    if s in NAMED:
        return (*NAMED[s], 1.0)
    m = re.fullmatch(r"gr[ae]y(\d{1,3})", s)  # Tk/X11 gray0..gray100
    if m and int(m.group(1)) <= 100:
        v = round(int(m.group(1)) * 255 / 100)
        return (v, v, v, 1.0)
    m = re.fullmatch(r"#([0-9a-f]{3,8})", s)
    if m and len(m.group(1)) in (3, 4, 6, 8):
        h = m.group(1)
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
        return (r, g, b, a)
    m = re.fullmatch(r"rgba?\(([^)]*)\)", s)
    if m:
        parts = [p for p in re.split(r"[\s,/]+", m.group(1)) if p]
        if len(parts) in (3, 4):
            rgb = [float(p[:-1]) * 2.55 if p.endswith("%") else float(p) for p in parts[:3]]
            a = 1.0
            if len(parts) == 4:
                a = float(parts[3][:-1]) / 100 if parts[3].endswith("%") else float(parts[3])
            return (*rgb, a)
    raise ValueError(f"unrecognised color: {text!r}")


def blend(fg: tuple, bg: tuple) -> tuple[float, float, float]:
    """Composite a translucent foreground over an opaque background."""
    a = fg[3]
    return tuple(fg[i] * a + bg[i] * (1 - a) for i in range(3))


def luminance(rgb: tuple) -> float:
    def channel(c: float) -> float:
        c = c / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(fg: tuple, bg: tuple) -> float:
    bg_rgb = bg[:3] if bg[3] >= 1 else blend(bg, (255, 255, 255, 1.0))  # assume a white canvas behind
    fg_rgb = blend(fg, (*bg_rgb, 1.0)) if fg[3] < 1 else fg[:3]
    hi, lo = sorted((luminance(fg_rgb), luminance(bg_rgb)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def to_hex(rgb: tuple) -> str:
    return "#" + "".join(f"{round(max(0, min(255, c))):02x}" for c in rgb[:3])


def suggest(fg: tuple, bg: tuple, target: float = 4.5) -> str | None:
    """Nearest foreground (moving toward black or white) that reaches the target ratio."""
    base = blend(fg, bg) if fg[3] < 1 else fg[:3]  # start from the color the user actually sees
    best = None
    for end in ((0, 0, 0), (255, 255, 255)):
        for step in range(1, 101):
            t = step / 100
            cand = tuple(round(base[i] + (end[i] - base[i]) * t) for i in range(3)) + (1.0,)
            if ratio(cand, bg) >= target:
                if best is None or t < best[0]:
                    best = (t, to_hex(cand))
                break
    return best[1] if best else None


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("colors", nargs="+", help="fg bg [fg bg ...]")
    ap.add_argument("--fix", action="store_true", help="suggest the nearest passing foreground for AA text")
    args = ap.parse_args(argv)
    if len(args.colors) % 2:
        ap.error("give colors in fg/bg pairs")
    worst = None
    for fg_text, bg_text in zip(args.colors[::2], args.colors[1::2]):
        try:
            fg, bg = parse_color(fg_text), parse_color(bg_text)
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 2
        r = ratio(fg, bg)
        worst = r if worst is None else min(worst, r)
        verdicts = ", ".join(f"{label} {'pass' if r >= need else 'FAIL'}" for label, need in THRESHOLDS)
        line = f"{fg_text} on {bg_text}: {r:.2f}:1  ({verdicts})"
        if args.fix and r < 4.5:
            line += f"\n  nearest AA text foreground: {suggest(fg, bg)}"
        print(line)
    return 0 if worst is not None and worst >= 4.5 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
