"""Thumbnails: the small pictures behind `thumb.src` (contracts common $defs.thumb, HUD v2 §5).

A thumbnail is a 320 px wide WebP (about 10 KB) kept in a cache folder **outside git**: by default
`<user data>/JarvisHub/thumbs` (next to Jarvis's other local data), or `$JARVIS_MEMORY_DIR/thumbs` when the
memory folder is set, or exactly `$JARVIS_THUMBS_DIR`. A folder inside the app or the repo is refused.

  thumb_path("file-pps7-p3.webp")  -> Path | None   what GET /api/thumb/<key> serves (server.py calls this)
  save_image(key, image)           -> Path          any Pillow image, scaled to 320 px wide, as WebP
  render_pdf_page(pdf, page, key)  -> Path | None   a PDF page (PyMuPDF), optionally just a band of it
  pptx_thumbnail(pptx, key)        -> Path | None   a deck's own docProps/thumbnail.jpeg
  key_for("file", "pps7", "p3")    -> "file-pps7-p3.webp"     src_for(key) -> "/api/thumb/file-pps7-p3.webp"

Made-up demo pictures (tools/make_demo_thumbs.py, never his files) live in ui/components/thumb/demo/ and are
served when the cache has no picture of that name (turn off with JARVIS_THUMBS_DEMO=0).
Pillow and PyMuPDF are installed with the hub; should either be missing, the makers return None and the UI
falls back to a monogram, initials or a room code.
"""
from __future__ import annotations

import io
import os
import re
import zipfile
from pathlib import Path

from . import settings

WIDTH = 320
TARGET_BYTES = 12_000  # "about 10 KB": quality steps down until the file fits (or the floor is reached)
QUALITIES = (72, 62, 52, 42)
SAFE_KEY = re.compile(r"^[a-z0-9][a-z0-9._:-]*\.webp$")


def demo_dir() -> Path:
    return settings.resource_path("ui", "components", "thumb", "demo")


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def cache_dir() -> Path:
    """Where thumbnails are cached. Never inside the app or repo folder (pictures of his things stay out of git)."""
    chosen = os.environ.get("JARVIS_THUMBS_DIR")
    if chosen:
        path = Path(chosen).expanduser()
    elif os.environ.get("JARVIS_MEMORY_DIR"):
        path = Path(os.environ["JARVIS_MEMORY_DIR"]).expanduser() / "thumbs"
    else:
        path = settings.data_dir() / "thumbs"
    if _inside(path, settings.base_dir()):
        path = settings.data_dir() / "thumbs"
    return path


def key_for(*parts: str) -> str:
    """A cache key from words: lower case, safe characters only, ending in .webp."""
    stem = "-".join(re.sub(r"[^a-z0-9]+", "-", str(p).lower()).strip("-") for p in parts if str(p).strip())
    return f"{stem or 'thumb'}.webp"


def src_for(key: str) -> str:
    return f"/api/thumb/{key}"


def _valid(key: str) -> bool:
    return bool(SAFE_KEY.match(key or "")) and ".." not in key


def thumb_path(key: str) -> Path | None:
    """The cached picture for `key` ("file-pps7-p3.webp"), else a demo picture of that name, else None."""
    if not _valid(key):
        return None
    for folder in (cache_dir(), demo_dir() if os.environ.get("JARVIS_THUMBS_DEMO", "1") != "0" else None):
        if folder is None:
            continue
        path = folder / key
        if path.is_file() and _inside(path, folder):
            return path
    return None


def _webp(image, width: int = WIDTH) -> bytes:
    from PIL import Image

    image = image.convert("RGB")
    if image.width != width:
        image = image.resize((width, max(1, round(image.height * width / image.width))), Image.LANCZOS)
    data = b""
    for quality in QUALITIES:
        buf = io.BytesIO()
        image.save(buf, "WEBP", quality=quality, method=6)
        data = buf.getvalue()
        if len(data) <= TARGET_BYTES:
            break
    return data


def save_image(key: str, image, folder: Path | None = None) -> Path:
    """Scale a Pillow image to 320 px wide and cache it as WebP under `key`. Written atomically."""
    if not _valid(key):
        raise ValueError(f"Not a thumbnail key: {key!r}")
    folder = folder or cache_dir()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / key
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(_webp(image))
    os.replace(tmp, path)
    return path


def render_pdf_page(pdf: str | Path, page: int, key: str, band: tuple[float, float] | None = None,
                    folder: Path | None = None) -> Path | None:
    """Render page `page` (1-based) of a PDF to a cached thumbnail. `band` = (top, bottom) as fractions of the
    page height, e.g. (0.4, 0.8) for the question's part of the page. None if PyMuPDF or Pillow is missing,
    or the file or page isn't there."""
    try:
        import pymupdf as fitz
        from PIL import Image
    except ImportError:
        return None
    try:
        with fitz.open(str(pdf)) as doc:
            if not 1 <= page <= doc.page_count:
                return None
            p = doc[page - 1]
            rect = p.rect
            clip = fitz.Rect(rect.x0, rect.y0 + rect.height * band[0], rect.x1, rect.y0 + rect.height * band[1]) if band else rect
            zoom = WIDTH / rect.width
            pix = p.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip, alpha=False)
            image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    except (RuntimeError, ValueError, OSError):
        return None
    return save_image(key, image, folder)


def pptx_thumbnail(pptx: str | Path, key: str, folder: Path | None = None) -> Path | None:
    """A slide deck's own thumbnail (docProps/thumbnail.jpeg, written by PowerPoint), cached. None if absent."""
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        with zipfile.ZipFile(pptx) as z:
            name = next((n for n in z.namelist() if n.lower().startswith("docprops/thumbnail.")), None)
            if not name or name.lower().endswith((".wmf", ".emf")):
                return None
            image = Image.open(io.BytesIO(z.read(name)))
            image.load()
    except (zipfile.BadZipFile, OSError, KeyError):
        return None
    return save_image(key, image, folder)
