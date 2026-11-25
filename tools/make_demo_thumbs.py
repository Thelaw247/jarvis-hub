"""Draw the demo's made-up thumbnails (HUD v2 §11: "made-up slide and page thumbnails drawn by a tool, never
his real files") into ui/components/thumb/demo/, as 320 px WebP files (~10 KB each).

  python tools/make_demo_thumbs.py            write every picture (overwrites)
  python tools/make_demo_thumbs.py --list     print the keys and what each one shows

The hub serves them at /api/thumb/<key> (jarvis_hub/thumbs.py falls back to this folder), so the demo and the
scenes can use `thumb.src = "/api/thumb/<key>"`. Everything drawn here is invented: no real course material.
Needs Pillow.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from jarvis_hub.thumbs import demo_dir, save_image  # noqa: E402

FONTS = ROOT / "ui" / "fonts"
W = 640  # drawn at twice the size, then scaled to 320 px by save_image

# colours for the pictures themselves (paper, ink, slide backgrounds); not UI colours, so not tokens
PAPER, INK, GREY, FAINT = (250, 250, 247), (28, 32, 40), (110, 116, 126), (205, 208, 214)
BLUE, RED, NAVY, ICE, AMBER = (40, 92, 170), (178, 52, 44), (16, 30, 52), (190, 228, 250), (232, 168, 60)


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    files = {"body": "atkinson-hyperlegible-next-latin-400-normal.woff2", "bold": "atkinson-hyperlegible-next-latin-700-normal.woff2",
             "display": "barlow-condensed-latin-600-normal.woff2", "mono": "jetbrains-mono-latin-400-normal.woff2",
             "head": "lexend-latin-500-normal.woff2"}
    return ImageFont.truetype(str(FONTS / files[name]), size)


def page(h: int = 480) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, h), PAPER)
    return img, ImageDraw.Draw(img)


def beam(d: ImageDraw.ImageDraw, x: int, y: int, length: int, load_at: float = 0.4) -> None:
    """A simply supported beam: bar, a pin and a roller, one point load."""
    d.rectangle([x, y, x + length, y + 12], outline=INK, width=3)
    for sx, roller in ((x, False), (x + length, True)):
        d.polygon([(sx, y + 12), (sx - 16, y + 40), (sx + 16, y + 40)], outline=INK, width=3)
        if roller:
            d.ellipse([sx - 14, y + 42, sx - 4, y + 52], outline=INK, width=2)
            d.ellipse([sx + 4, y + 42, sx + 14, y + 52], outline=INK, width=2)
        else:
            d.line([sx - 22, y + 42, sx + 22, y + 42], fill=INK, width=3)
    lx = x + int(length * load_at)
    d.line([lx, y - 60, lx, y - 6], fill=RED, width=4)
    d.polygon([(lx, y - 2), (lx - 9, y - 18), (lx + 9, y - 18)], fill=RED)
    d.text((lx + 10, y - 66), "12 kN", font=font("bold", 22), fill=RED)
    d.text((x - 10, y + 58), "A", font=font("bold", 22), fill=INK)
    d.text((x + length - 6, y + 58), "B", font=font("bold", 22), fill=INK)


def lines(d: ImageDraw.ImageDraw, x: int, y: int, texts: list[str], size: int = 22, gap: int = 34, fill=INK) -> int:
    for t in texts:
        d.text((x, y), t, font=font("body", size), fill=fill)
        y += gap
    return y


def pps7_p1() -> Image.Image:
    img, d = page()
    d.text((40, 34), "GE 122 · Problem-Solving Set 7", font=font("bold", 30), fill=INK)
    d.text((40, 76), "Statics · due Wednesday 8:00 pm · show your free-body diagrams", font=font("body", 19), fill=GREY)
    d.line([40, 112, W - 40, 112], fill=FAINT, width=2)
    y = lines(d, 40, 132, ["1. A beam AB of length 4 m carries a point load", "    of 12 kN at 1.6 m from A. Find the reactions."])
    beam(d, 120, y + 90, 400)
    return img


def pps7_p3() -> Image.Image:
    img, d = page()
    d.text((W - 150, 24), "Page 3 of 3", font=font("body", 18), fill=GREY)
    lines(d, 40, 30, ["6. Repeat question 5 with the roller at C."], fill=GREY)
    d.line([40, 80, W - 40, 80], fill=FAINT, width=2)
    d.text((40, 100), "7.", font=font("bold", 40), fill=BLUE)
    y = lines(d, 92, 104, ["The beam below carries a point load and a", "uniform load of 3 kN/m over BC. Find the", "reactions at A and C."], size=22)
    beam(d, 110, y + 80, 420, load_at=0.3)
    for i in range(6):  # the distributed load over the right half
        x = 110 + 230 + i * 36
        d.line([x, y + 40, x, y + 74], fill=BLUE, width=3)
        d.polygon([(x, y + 78), (x - 6, y + 68), (x + 6, y + 68)], fill=BLUE)
    d.line([110 + 230, y + 40, 110 + 410, y + 40], fill=BLUE, width=3)
    return img


def pps7_hints() -> Image.Image:
    img, d = page()
    d.text((40, 34), "Hints for PPS 7", font=font("bold", 30), fill=INK)
    d.line([40, 80, W - 40, 80], fill=FAINT, width=2)
    lines(d, 40, 104, ["• Start with the free-body diagram.", "• Replace a uniform load by one force at", "   the middle of the loaded length.",
                       "• Sum moments about a support first:", "   one unknown at a time."], size=23, gap=38)
    return img


def lab4() -> Image.Image:
    img, d = page()
    d.text((40, 30), "CHEM 142 · Lab report 4", font=font("bold", 28), fill=INK)
    d.text((40, 72), "Results", font=font("head", 26), fill=BLUE)
    lines(d, 40, 112, ["Absorbance fell steadily over six minutes,", "consistent with a first-order reaction."], size=20, gap=30)
    # a small plot: decaying points and a fitted curve
    ox, oy, gw, gh = 70, 420, 500, 200
    d.line([ox, oy, ox + gw, oy], fill=INK, width=2)
    d.line([ox, oy, ox, oy - gh], fill=INK, width=2)
    pts = [(ox + i * gw / 10, oy - gh * math.exp(-i / 4)) for i in range(11)]
    d.line(pts, fill=BLUE, width=3)
    for i, (px, py) in enumerate(pts):
        if i % 2 == 0:
            d.ellipse([px - 5, py - 5 + (6 if i % 4 else -4), px + 5, py + 5 + (6 if i % 4 else -4)], outline=RED, width=2)
    d.text((ox + gw - 70, oy + 8), "t (min)", font=font("body", 18), fill=GREY)
    return img


def slide(title: str, sub: str, draw) -> Image.Image:
    img = Image.new("RGB", (W, 360), (244, 246, 250))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 54], fill=NAVY)
    d.text((24, 12), sub, font=font("display", 28), fill=ICE)
    d.text((24, 76), title, font=font("display", 60), fill=NAVY)
    draw(d)
    return img


def truss(d: ImageDraw.ImageDraw, x: int = 320, y: int = 300, w: int = 280, h: int = 120, ink=NAVY) -> None:
    n = 4
    top = [(x + i * w / n + w / (2 * n), y - h) for i in range(n)]
    bot = [(x + i * w / n, y) for i in range(n + 1)]
    for i in range(n):
        d.line([bot[i], bot[i + 1]], fill=ink, width=4)
        d.line([bot[i], top[i]], fill=ink, width=3)
        d.line([top[i], bot[i + 1]], fill=ink, width=3)
        if i:
            d.line([top[i - 1], top[i]], fill=ink, width=4)
    for p in bot + top:
        d.ellipse([p[0] - 5, p[1] - 5, p[0] + 5, p[1] + 5], fill=AMBER)


def ge122_l21() -> Image.Image:
    def draw(d):
        lines(d, 24, 170, ["Method of joints", "Method of sections", "Zero-force members"], size=24, gap=38, fill=INK)
        truss(d)
    return slide("Frames and trusses", "GE 122 · Lecture 21", draw)


def chem142_l18() -> Image.Image:
    def draw(d):
        lines(d, 24, 170, ["Rate laws", "Half-life", "First order: ln[A] vs t"], size=24, gap=38, fill=INK)
        pts = [(330 + i * 26, 320 - 150 * math.exp(-i / 3)) for i in range(11)]
        d.line([330, 320, 610, 320], fill=INK, width=2)
        d.line([330, 320, 330, 160], fill=INK, width=2)
        d.line(pts, fill=BLUE, width=4)
    return slide("Reaction rates", "CHEM 142 · Lecture 18", draw)


def video_frame() -> Image.Image:
    img = ge122_l21()
    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle([0, 318, W, 360], fill=(10, 16, 28, 220))
    d.rectangle([20, 336, W - 20, 342], fill=(120, 130, 150, 255))
    d.rectangle([20, 336, 20 + int((W - 40) * 0.42), 342], fill=(56, 200, 255, 255))
    d.polygon([(W / 2 - 26, 140), (W / 2 - 26, 210), (W / 2 + 30, 175)], fill=(10, 16, 28, 200))
    return img


def course(motif) -> Image.Image:
    img = Image.new("RGB", (W, W), NAVY)
    d = ImageDraw.Draw(img)
    for i in range(0, W, 40):  # a quiet grid
        d.line([i, 0, i, W], fill=(26, 44, 72), width=1)
        d.line([0, i, W, i], fill=(26, 44, 72), width=1)
    motif(d)  # no lettering: the UI lays the course code over the picture as its big label
    return img


def ge_motif(d):
    truss(d, x=120, y=360, w=400, h=180, ink=ICE)


def chem_motif(d):
    centres = [(320, 200), (220, 260), (420, 260), (320, 320), (220, 140), (420, 140)]
    for a, b in ((0, 1), (0, 2), (0, 3), (1, 4), (2, 5)):
        d.line([centres[a], centres[b]], fill=ICE, width=6)
    for cx, cy in centres:
        d.ellipse([cx - 26, cy - 26, cx + 26, cy + 26], fill=AMBER if (cx, cy) == centres[0] else (56, 200, 255))


def math_motif(d):
    """A curve with the area under part of it shaded: an integral, drawn rather than typed."""
    f = lambda x: 300 - 90 * math.sin((x - 80) / 70) - (x - 80) * 0.15  # noqa: E731
    area = [(260, 380)] + [(x, f(x)) for x in range(260, 461, 10)] + [(460, 380)]
    d.polygon(area, fill=(40, 74, 120))
    d.line([(x, f(x)) for x in range(80, 581, 5)], fill=(56, 200, 255), width=6)
    d.line([60, 380, 580, 380], fill=ICE, width=3)
    for x in (260, 460):
        d.line([x, 380, x, f(x)], fill=AMBER, width=4)


def cedar_design() -> Image.Image:
    img = Image.new("RGB", (W, 360), PAPER)
    d = ImageDraw.Draw(img)
    d.line([(60, 300), (580, 70)], fill=INK, width=4)  # the branch
    for i in range(1, 9):
        t = i / 9
        bx, by = 60 + 520 * t, 300 - 230 * t
        for side in (-1, 1):
            leaf = [(bx + k * 7, by + side * (k * 5) - k * 2) for k in range(9)]
            d.line(leaf, fill=INK, width=3)
            for k in range(1, 9, 2):  # little scale-leaves
                lx, ly = leaf[k]
                d.line([lx, ly, lx + 8, ly + side * 10], fill=INK, width=2)
    d.rectangle([12, 12, W - 12, 348], outline=FAINT, width=2)
    return img


PICTURES = {
    "file-pps7-p1.webp": ("page", "PPS 7, page 1: question 1, a beam on two supports", pps7_p1),
    "file-pps7-p3.webp": ("page", "PPS 7, page 3: question 7, a beam with a point load and a uniform load", pps7_p3),
    "file-pps7-hints-p1.webp": ("page", "PPS 7 hints, page 1", pps7_hints),
    "file-lab4-p1.webp": ("page", "Lab report 4, the Results heading and a decay plot", lab4),
    "slides-ge122-l21.webp": ("slide", "GE 122 lecture 21 title slide: Frames and trusses", ge122_l21),
    "slides-chem142-l18.webp": ("slide", "CHEM 142 lecture 18 slide: Reaction rates", chem142_l18),
    "video-ge122-l21.webp": ("video", "GE 122 lecture 21 video, paused at the trusses slide", video_frame),
    "course-ge-122.webp": ("course", "GE 122 course picture: a truss", lambda: course(ge_motif)),
    "course-chem-142.webp": ("course", "CHEM 142 course picture: a molecule", lambda: course(chem_motif)),
    "course-math-133.webp": ("course", "MATH 133 course picture: a curve with the area under it shaded", lambda: course(math_motif)),
    "design-cedar.webp": ("design", "Plotter design: a cedar branch line drawing", cedar_design),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list", action="store_true", help="print the keys and what each one shows")
    args = parser.parse_args()
    if args.list:
        for key, (kind, alt, _draw) in PICTURES.items():
            print(f"{key:28} {kind:7} {alt}")
        return 0
    folder = demo_dir()
    for key, (_kind, _alt, draw) in PICTURES.items():
        path = save_image(key, draw(), folder)
        print(f"{path.relative_to(ROOT)}  {path.stat().st_size / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
