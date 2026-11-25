"""The question index of a practice-set PDF, built once when the file is filed (HUD v2 §10.1).

    build_index(pdf) -> {"pages", "page_sizes", "questions": [{label, n, part, page, y, x, w, h, size}], ...}
    file_pdf(file_id, pdf) -> the index, saved to the cache, plus a thumbnail of each question's page

Finds question headings ("Question 7", "Problem 3a", "Q7", "7.", and "(a)" sub-parts) with PyMuPDF and keeps
only the ones that look like headings: at the left margin, in a normal-or-larger font, with numbers that go up.
`page` counts from 1; `y` is the top of the heading in PDF points from the top of the page (the reader's units).
Opening a PDF reads the saved index and does no extra work. Nothing here is ever written into the repo: the
index and the thumbnails live in Jarvis's cache folder.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from collections import Counter
from pathlib import Path

from . import settings

INDEX_V = 1
THUMB_WIDTH = 240  # px: a small WebP, like every other thumb (HUD v2 §5)
MAX_GAP = 3  # a question number may skip at most this many (a missing heading) and still count as ascending
MARGIN_SLACK = 18.0  # pt right of the left margin a question heading may start
PART_SLACK = 60.0  # pt right of the left margin a sub-part "(a)" may start (they are often indented)
MIN_SIZE = 0.9  # a heading's font is at least this share of the body size (footnotes and labels are smaller)

# "Question 7", "QUESTION 7:", "Problem 3a", "Problem 3(b)", "Exercise 2", "Q7", "Q. 7", "Q7b" (not "Problem 3.2")
KEYWORD = re.compile(r"^(?i:question|problem|exercise|q)\s*\.?\s*(\d{1,3})(?:([a-h])|\s?\(([a-h])\))?(?![\d.]\d)"
                     r"(?=$|[\s.:)\-–—])")
NUMBER = re.compile(r"^(\d{1,2})\s*[.)](?=\s|$|[A-Z(\[])")  # "7." or "7)" at the start of a line ("10.Find" too)
PART = re.compile(r"^\(?([a-h])\)(?=\s|$)")  # "(a)" or "a)"
SOLUTIONS = re.compile(r"\bsolutions?\b", re.IGNORECASE)


def _fitz():
    import pymupdf  # imported late: the hub runs without it until a PDF needs indexing

    return pymupdf


def _lines(doc) -> list[dict]:
    """Every text line with its page, box, font size and text (document order)."""
    out = []
    for number, page in enumerate(doc, 1):
        for block in page.get_text("dict", sort=True).get("blocks", []):
            for line in block.get("lines", []):
                spans = [s for s in line.get("spans", []) if s.get("text", "").strip()]
                if not spans:
                    continue
                text = "".join(s["text"] for s in spans).strip()
                x0, y0, x1, y1 = line["bbox"]
                out.append({"page": number, "x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0, "text": text,
                            "size": max(s["size"] for s in spans), "chars": len(text)})
    return out


def _body_size(lines: list[dict]) -> float:
    sizes = Counter()
    for line in lines:
        sizes[round(line["size"], 1)] += line["chars"]
    return sizes.most_common(1)[0][0] if sizes else 11.0


def _left_margin(lines: list[dict], body: float) -> float:
    xs = sorted(line["x"] for line in lines if abs(line["size"] - body) <= body * 0.2) or sorted(line["x"] for line in lines)
    return xs[len(xs) // 20] if xs else 72.0  # the 5th percentile: one odd line doesn't move the margin


def _candidates(lines: list[dict], body: float, margin: float, heights: list[float]) -> tuple[list, list, list]:
    keyword, number, part = [], [], []
    for line in lines:
        if line["size"] < body * MIN_SIZE:
            continue
        text, x = line["text"], line["x"]
        page_h = heights[line["page"] - 1]
        if (m := KEYWORD.match(text)) and x <= margin + MARGIN_SLACK:
            keyword.append((int(m.group(1)), m.group(2) or m.group(3), line))
        elif (m := NUMBER.match(text)) and x <= margin + MARGIN_SLACK and page_h * 0.05 < line["y"] < page_h * 0.94:
            number.append((int(m.group(1)), None, line))  # not in the header or footer band (page numbers)
        elif (m := PART.match(text)) and x <= margin + PART_SLACK:
            part.append((None, m.group(1).lower(), line))
    return keyword, number, part


def _ascending(found: list[tuple], first_max: int) -> list[tuple]:
    """Keep headings whose numbers go up (a restart or a jump backwards is a list inside a question)."""
    kept, last = [], None
    for n, letter, line in found:
        key = (n, letter or "")
        if last is None:
            if n > first_max:
                continue
        elif not (last < key and n - last[0] <= MAX_GAP):
            continue
        kept.append((n, letter, line))
        last = key
    return kept


def _entry(n: int, letter: str | None, line: dict) -> dict:
    return {"label": f"Q{n}{letter or ''}", "n": n, "part": letter, "page": line["page"],
            "y": round(line["y"], 1), "x": round(line["x"], 1), "w": round(line["w"], 1), "h": round(line["h"], 1),
            "size": round(line["size"], 1)}


def _with_parts(tops: list[tuple], parts: list[tuple]) -> list[dict]:
    """Questions in order, each followed by its sub-parts ("(a)", "(b)"…, letters in order from a)."""
    pos = lambda line: (line["page"], line["y"])  # noqa: E731
    out = []
    for i, (n, letter, line) in enumerate(tops):
        out.append(_entry(n, letter, line))
        if letter:  # "Problem 3a" style: the heading is the part
            continue
        end = pos(tops[i + 1][2]) if i + 1 < len(tops) else (10**6, 0)
        expect = "a"
        for _, part, pline in parts:
            if pos(line) < pos(pline) < end and part == expect:
                out.append(_entry(n, part, pline))
                expect = chr(ord(expect) + 1)
    return out


def build_index(pdf: str | Path) -> dict:
    """Read the PDF once and find its questions. ~1 ms a page."""
    fitz, started = _fitz(), time.perf_counter()
    with fitz.open(str(pdf)) as doc:
        sizes = [[round(p.rect.width, 1), round(p.rect.height, 1)] for p in doc]
        lines = _lines(doc)
    body = _body_size(lines)
    margin = _left_margin(lines, body)
    keyword, number, parts = _candidates(lines, body, margin, [h for _, h in sizes])
    tops = _ascending(keyword, first_max=50)
    if len(tops) < 2:  # no "Question N" headings: fall back to "7." numbering, which must start near 1
        tops = _ascending(number, first_max=3)
    questions = _with_parts(tops, parts)
    first_page = " ".join(line["text"] for line in lines if line["page"] == 1)[:600]
    return {"v": INDEX_V, "pages": len(sizes), "page_sizes": sizes, "questions": questions,
            "solutions": bool(SOLUTIONS.search(first_page)), "body_size": body,
            "ms": round((time.perf_counter() - started) * 1000, 1)}


def question_at(index: dict, page: int, y: float) -> dict | None:
    """The question whose part of the page holds (page, y): the last heading at or above that spot."""
    best = None
    for q in index.get("questions", []):
        if (q["page"], q["y"]) <= (page, y + 1):
            best = q
    return best


def top_questions(index: dict) -> list[dict]:
    return [q for q in index.get("questions", []) if not q["part"] or not any(
        o["n"] == q["n"] and not o["part"] for o in index["questions"])]


# ---- the cache: Jarvis's own folder, never the repo ---------------------------------------------------
def cache_dir(*parts: str) -> Path:
    path = settings.data_dir().joinpath("cache", *parts)
    path.mkdir(parents=True, exist_ok=True)
    return path


def thumbs_dir() -> Path:
    """Where page thumbnails go. N5a's jarvis_hub/thumbs.py owns the thumbnail cache; use its folder if it is there."""
    try:
        from . import thumbs  # type: ignore[attr-defined]

        folder = getattr(thumbs, "cache_dir", None)
        if callable(folder):
            return Path(folder())
    except ImportError:
        pass
    return cache_dir("thumbs")


def _fingerprint(pdf: Path) -> str:
    stat = pdf.stat()
    return hashlib.sha1(f"{pdf.resolve()}|{stat.st_size}|{stat.st_mtime_ns}".encode()).hexdigest()[:16]


def index_path(file_id: str) -> Path:
    return cache_dir("qindex") / f"{file_id}.json"


def load_index(file_id: str) -> dict | None:
    try:
        return json.loads(index_path(file_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def thumb_key(file_id: str, page: int) -> str:
    return f"{file_id}-p{page}.webp"


def render_thumbs(pdf: str | Path, file_id: str, pages: list[int], width: int = THUMB_WIDTH) -> dict[int, str]:
    """A small WebP of each page (key `<file id>-p<page>.webp`), for thumb.src = /api/thumb/<key>.
    Uses N5a's jarvis_hub/thumbs.py (render_pdf_page) when it is there, so every thumbnail is made one way.
    Needs Pillow for WebP; without it there are no thumbnails (the card shows its page monogram instead)."""
    try:
        from . import thumbs as shared  # type: ignore[attr-defined]
    except ImportError:
        shared = None
    if shared is not None and callable(getattr(shared, "render_pdf_page", None)):
        made = {n: thumb_key(file_id, n) for n in sorted(set(pages))}
        return {n: key for n, key in made.items() if shared.render_pdf_page(pdf, n, key)}
    try:
        from PIL import Image
    except ImportError:
        return {}
    fitz, folder, keys = _fitz(), thumbs_dir(), {}
    with fitz.open(str(pdf)) as doc:
        for number in sorted(set(pages)):
            if not 1 <= number <= len(doc):
                continue
            page = doc[number - 1]
            pix = page.get_pixmap(matrix=fitz.Matrix(width / page.rect.width, width / page.rect.width), alpha=False)
            image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            key = thumb_key(file_id, number)
            image.save(folder / key, "WEBP", quality=70, method=4)
            keys[number] = key
    return keys


def file_pdf(file_id: str, pdf: str | Path, thumbs: bool = True) -> dict:
    """Filing time (class-sync, or the demo): index the PDF and render its question pages. Cached by content."""
    pdf = Path(pdf)
    print_ = _fingerprint(pdf)
    cached = load_index(file_id)
    if cached and cached.get("fingerprint") == print_:
        missing = [int(n) for n, key in (cached.get("thumbs") or {}).items() if not (thumbs_dir() / key).is_file()]
        if thumbs and missing:  # the picture cache was cleared or moved: draw the pages again, keep the index
            render_thumbs(pdf, file_id, missing)
        return cached
    index = build_index(pdf)
    index["fingerprint"] = print_
    index["file_id"] = file_id
    if thumbs:
        pages = sorted({q["page"] for q in index["questions"]} | {1})
        index["thumbs"] = {str(k): v for k, v in render_thumbs(pdf, file_id, pages).items()}
    index_path(file_id).write_text(json.dumps(index), encoding="utf-8")
    return index
