"""Sample colors from a screenshot so contrast can be measured, not guessed (rule A11Y-01).

Usage:
    python pixel_colors.py shot.png 120,48 300,52            # hex color at each x,y point
    python pixel_colors.py shot.png --box 100,40,260,60      # darkest and lightest pixel in a box

For text, put the box tightly around a few glyphs: the darkest pixel approximates the text color and the
lightest the background (swap them for light-on-dark text). Anti-aliasing lightens glyph edges, so the
darkest pixel is the fairest estimate. Feed the two colors to contrast.py. Needs Pillow (pip install pillow).
Screenshots taken with display scaling are in device pixels: divide by the scale factor to get CSS px.
"""

from __future__ import annotations

import argparse
import sys

try:
    from PIL import Image
except ImportError:  # pragma: no cover - depends on the environment
    sys.exit("Pillow is not installed: pip install pillow (or uv run --with pillow python pixel_colors.py ...)")


def hex_of(px) -> str:
    return "#" + "".join(f"{c:02x}" for c in px[:3])


def brightness(px) -> float:
    return 0.2126 * px[0] + 0.7152 * px[1] + 0.0722 * px[2]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image")
    ap.add_argument("points", nargs="*", help="x,y pixel positions")
    ap.add_argument("--box", action="append", default=[], help="x0,y0,x1,y1: report darkest and lightest pixel")
    args = ap.parse_args(argv)
    img = Image.open(args.image).convert("RGB")
    print(f"{args.image}: {img.width}x{img.height} px")
    for point in args.points:
        x, y = (int(v) for v in point.split(","))
        print(f"{x},{y}: {hex_of(img.getpixel((x, y)))}")
    for box in args.box:
        x0, y0, x1, y1 = (int(v) for v in box.split(","))
        crop = img.crop((x0, y0, x1, y1))
        access = crop.load()
        pixels = [access[x, y] for x in range(crop.width) for y in range(crop.height)]
        dark, light = min(pixels, key=brightness), max(pixels, key=brightness)
        print(f"box {box}: darkest {hex_of(dark)}, lightest {hex_of(light)}"
              f"  ->  python contrast.py {hex_of(dark)} {hex_of(light)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
