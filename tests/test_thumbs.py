"""Thumbnails (N5a, HUD v2 §5): the cache lives outside git, keys can't walk the disk, PDFs and decks become
320 px WebP files of about 10 KB, and the made-up demo pictures are served when the cache has none."""
import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from jarvis_hub import settings, thumbs

PIL = pytest.importorskip("PIL.Image")
ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def cache(tmp_path, monkeypatch):
    folder = tmp_path / "thumbs"
    monkeypatch.setenv("JARVIS_THUMBS_DIR", str(folder))
    return folder


def picture(w=900, h=600):
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (w, h), (250, 250, 247))
    d = ImageDraw.Draw(img)
    for i in range(0, w, 30):
        d.line([i, 0, w - i, h], fill=(20, 40, 90), width=3)
    return img


def test_the_cache_is_outside_the_repo_and_can_be_moved(cache, monkeypatch):
    assert thumbs.cache_dir() == cache
    monkeypatch.delenv("JARVIS_THUMBS_DIR")
    monkeypatch.setenv("JARVIS_MEMORY_DIR", str(cache.parent / "memory"))
    assert thumbs.cache_dir() == cache.parent / "memory" / "thumbs"
    monkeypatch.delenv("JARVIS_MEMORY_DIR")
    monkeypatch.setattr(settings, "data_dir", lambda: cache.parent / "data")
    assert thumbs.cache_dir() == cache.parent / "data" / "thumbs"
    # a folder inside the app or repo is refused: pictures of his things never land where git could see them
    monkeypatch.setenv("JARVIS_THUMBS_DIR", str(ROOT / "ui" / "thumbs"))
    assert thumbs.cache_dir() == cache.parent / "data" / "thumbs"


def test_keys_are_safe_and_never_walk_the_disk(cache):
    assert thumbs.key_for("file", "PPS 7", "p3") == "file-pps-7-p3.webp"
    assert thumbs.src_for("file-pps7-p3.webp") == "/api/thumb/file-pps7-p3.webp"
    for bad in ("../secret.webp", "a/b.webp", "..webp", "x.png", "", "UPPER.webp", "x..y.webp"):
        assert thumbs.thumb_path(bad) is None, bad
    with pytest.raises(ValueError):
        thumbs.save_image("../x.webp", picture())


def test_saved_pictures_are_small_webp_320_wide(cache):
    path = thumbs.save_image("test-pic.webp", picture())
    assert path.parent == cache and thumbs.thumb_path("test-pic.webp") == path
    from PIL import Image

    with Image.open(path) as img:
        assert img.format == "WEBP" and img.width == 320 and img.height == round(600 * 320 / 900)
    assert path.stat().st_size <= 14_000  # "about 10 KB"
    assert not list(cache.glob("*.tmp"))  # written atomically


def test_a_pdf_page_or_a_band_of_it_becomes_a_thumbnail(cache, tmp_path):
    fitz = pytest.importorskip("fitz")
    pdf = tmp_path / "set.pdf"
    with fitz.open() as doc:
        for n in range(1, 4):
            page = doc.new_page(width=612, height=792)
            page.insert_text((72, 100), f"Question {n}", fontsize=28)
        doc.save(pdf)
    full = thumbs.render_pdf_page(pdf, 3, "file-set-p3.webp")
    band = thumbs.render_pdf_page(pdf, 1, "file-set-q1.webp", band=(0.0, 0.25))
    from PIL import Image

    with Image.open(full) as a, Image.open(band) as b:
        assert a.width == b.width == 320 and a.height > 400 and b.height < 110
    assert thumbs.render_pdf_page(pdf, 9, "nope.webp") is None  # no such page
    assert thumbs.render_pdf_page(tmp_path / "missing.pdf", 1, "nope.webp") is None
    assert thumbs.thumb_path("nope.webp") is None


def test_a_slide_deck_gives_its_own_thumbnail(cache, tmp_path):
    deck = tmp_path / "l21.pptx"
    buf = io.BytesIO()
    picture(256, 192).save(buf, "JPEG")
    with zipfile.ZipFile(deck, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("docProps/thumbnail.jpeg", buf.getvalue())
    path = thumbs.pptx_thumbnail(deck, "slides-l21.webp")
    assert path and path.name == "slides-l21.webp" and path.stat().st_size > 0
    bare = tmp_path / "bare.pptx"
    with zipfile.ZipFile(bare, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
    assert thumbs.pptx_thumbnail(bare, "slides-bare.webp") is None
    (tmp_path / "broken.pptx").write_bytes(b"not a zip")
    assert thumbs.pptx_thumbnail(tmp_path / "broken.pptx", "slides-broken.webp") is None


def test_demo_pictures_are_served_by_the_thumb_route_and_the_cache_wins(cache, monkeypatch):
    from jarvis_hub.server import create_app

    demo = thumbs.demo_dir()
    assert (demo / "file-pps7-p3.webp").is_file(), "run python tools/make_demo_thumbs.py"
    with TestClient(create_app(autoplay=False, speed=0), base_url="http://127.0.0.1") as client:
        r = client.get("/api/thumb/file-pps7-p3.webp")
        assert r.status_code == 200 and r.content[:4] == b"RIFF" and r.content[8:12] == b"WEBP"
        assert client.get("/api/thumb/not-made.webp").status_code == 404
        assert client.get("/api/thumb/..%2Fthumb.js").status_code == 404
        mine = thumbs.save_image("file-pps7-p3.webp", picture())  # his own cached picture beats the demo one
        assert thumbs.thumb_path("file-pps7-p3.webp") == mine
        assert client.get("/api/thumb/file-pps7-p3.webp").content == mine.read_bytes()
        monkeypatch.setenv("JARVIS_THUMBS_DEMO", "0")
        assert client.get("/api/thumb/course-ge-122.webp").status_code == 404


def test_every_demo_picture_is_small_and_listed_by_the_tool():
    import importlib.util

    spec = importlib.util.spec_from_file_location("make_demo_thumbs", ROOT / "tools" / "make_demo_thumbs.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    on_disk = {p.name for p in thumbs.demo_dir().glob("*.webp")}
    assert on_disk == set(tool.PICTURES)
    for name in on_disk:
        assert (thumbs.demo_dir() / name).stat().st_size <= 14_000, name
        kind, alt, _draw = tool.PICTURES[name]
        assert kind in {"page", "slide", "course", "video", "design"} and alt
