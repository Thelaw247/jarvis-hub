"""Draws the app icon (a terracotta orb ring with one leaf on cream paper) and writes ui/icons/app.ico.
Run:  python tools/make_icon.py      (needs Pillow; the .ico is committed, so this is only for changes)
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
CANVAS, RING, LEAF = (243, 236, 223, 255), (180, 81, 42, 255), (92, 148, 113, 255)  # --canvas, --accent, --leaf


def draw(size: int = 256) -> Image.Image:
    scale = 4  # draw large, shrink for smooth edges
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, s - 1, s - 1), radius=int(s * 0.22), fill=CANVAS)
    c, r, w = s / 2, s * 0.27, int(s * 0.078)
    d.ellipse((c - r, c - r, c + r, c + r), outline=RING, width=w)
    leaf = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ld = ImageDraw.Draw(leaf)
    ld.ellipse((c, c - s * 0.075, c + s * 0.28, c + s * 0.075), fill=LEAF)
    leaf = leaf.rotate(45, center=(c, c), resample=Image.BICUBIC)
    img.alpha_composite(leaf)
    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    out = ROOT / "ui" / "icons" / "app.ico"
    draw(256).save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
