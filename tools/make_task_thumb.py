"""Draw the demo task's made-up Fusion view (the phone stand) into ui/components/agent-task/demo/task-stand.webp.

  python tools/make_task_thumb.py

Invented picture for the demo only (HUD v2 §11). The colours are the picture's own (a CAD viewport), not UI colours.
Needs Pillow.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "ui" / "components" / "agent-task" / "demo" / "task-stand.webp"
W, H = 960, 540  # drawn at 2x, saved at 480 px wide
BG, GRID, AXIS = (36, 40, 46), (54, 59, 66), (92, 98, 108)
TOP, LEFT, RIGHT, EDGE = (196, 202, 210), (150, 157, 167), (120, 127, 138), (70, 140, 220)


def iso(x: float, y: float, z: float) -> tuple[float, float]:
    """A simple isometric projection (mm → px), centred in the view."""
    s = 3.1
    return (W / 2 + (x - y) * 0.866 * s, H * 0.70 + (x + y) * 0.5 * s - z * s)


def box(d: ImageDraw.ImageDraw, x0, y0, z0, x1, y1, z1) -> None:
    p = {k: iso(*k) for k in [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]}
    faces = [((x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1), LEFT),
             ((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1), RIGHT),
             ((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1), TOP)]
    for *corners, fill in faces:
        d.polygon([p[c] for c in corners], fill=fill, outline=EDGE)


def main() -> int:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for i in range(-80, 81, 10):  # the ground grid
        d.line([iso(i, -80, 0), iso(i, 80, 0)], fill=GRID, width=1)
        d.line([iso(-80, i, 0), iso(80, i, 0)], fill=GRID, width=1)
    d.line([iso(0, 0, 0), iso(70, 0, 0)], fill=AXIS, width=2)
    d.line([iso(0, 0, 0), iso(0, 70, 0)], fill=AXIS, width=2)
    box(d, -45, -35, 0, 45, 35, 6)          # the 90 × 70 mm base, 6 mm thick
    box(d, -45, -35, 6, 45, -23, 18)        # the 12 mm lip that holds the phone (farther, so drawn first)
    box(d, -45, 20, 6, 45, 32, 62)          # the back rest
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.resize((W // 2, H // 2), Image.LANCZOS).save(OUT, "WEBP", quality=72, method=6)
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
