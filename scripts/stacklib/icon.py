"""The stack's icon: the tray's circle with a white "A". One drawing for the tray, its windows and the PAS-*.exe copies."""
from __future__ import annotations

import io

COLORS = {"ok": "#2e9d57", "warn": "#d99a1e", "bad": "#c94a3d", "idle": "#8a8f98"}  # tray icon fills
BRAND = COLORS["ok"]  # the colour of the icon outside the tray (programs in Task Manager, shortcuts, window icons)
ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def make_icon(color: str, size: int = 64):
    """The tray icon at `size` pixels (PIL RGBA image). At 64 px it is the tray's original drawing."""
    from PIL import Image, ImageDraw

    s = size / 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((4 * s, 4 * s, 60 * s, 60 * s), fill=color)
    d.polygon([(x * s, y * s) for x, y in ((32, 14), (48, 50), (40, 50), (32, 30), (24, 50), (16, 50))], fill="white")  # "A"
    return img


def ico_bytes(color: str = BRAND) -> bytes:
    """A Windows .ico with every size Explorer and Task Manager ask for, drawn at 256 px and scaled down."""
    buf = io.BytesIO()
    make_icon(color, 256).save(buf, format="ICO", sizes=[(n, n) for n in ICO_SIZES])
    return buf.getvalue()
