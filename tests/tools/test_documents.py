"""read_document (TOOLS §8): PDFs with pages, long ones cut to what matters, scans by vision, folders enforced."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pymupdf as fitz
import pytest

from jarvis.documents import DocumentReader
from jarvis.tools import Registry, ToolContext, ToolError


def pdf(path: Path, pages: list[str], scan_page: int | None = None) -> Path:
    doc = fitz.open()
    for i, text in enumerate(pages, start=1):
        page = doc.new_page()
        if i == scan_page:  # an image only, no text layer
            pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 40, 40), 0)
            pix.clear_with(200)
            page.insert_image(fitz.Rect(50, 50, 300, 300), pixmap=pix)
        else:
            page.insert_textbox(fitz.Rect(36, 36, 576, 806), text, fontsize=6)
    doc.save(path)
    return path


def test_a_pdf_comes_back_with_page_numbers(tmp_path):
    p = pdf(tmp_path / "lab.pdf", ["Lab 5 Trusses", "Method of joints: sum of forces", "Report due Friday"])
    doc = asyncio.run(DocumentReader([tmp_path], tmp_path / "dl").read(str(p)))
    text = doc.as_text()
    assert doc.page_count == 3 and "--- page 2 ---" in text and "Method of joints" in text


def test_a_long_document_returns_the_pages_that_answer_the_question(tmp_path):
    pages = [f"Filler page {i} " + "lorem ipsum " * 300 for i in range(1, 40)]
    pages[27] = "Safety: goggles are required in the lab at all times. " + "x " * 50
    p = pdf(tmp_path / "manual.pdf", pages)
    reader = DocumentReader([tmp_path], tmp_path / "dl")
    doc = asyncio.run(reader.read(str(p), question="are goggles required"))
    assert any(n == 28 for n, _ in doc.pages) and doc.pages_returned < 10
    assert "match the question" in doc.note
    some = asyncio.run(reader.read(str(p), pages="3-4"))
    assert [n for n, _ in some.pages] == [3, 4]
    with pytest.raises(ToolError):
        asyncio.run(reader.read(str(p), pages="90"))


def test_a_scanned_page_is_read_by_vision(tmp_path):
    p = pdf(tmp_path / "scan.pdf", ["Typed page", ""], scan_page=2)
    seen = []

    async def vision(png: bytes, prompt: str) -> str:
        seen.append(png[:4])
        return "Handwritten: F = ma"
    doc = asyncio.run(DocumentReader([tmp_path], tmp_path / "dl", vision=vision).read(str(p)))
    assert "F = ma" in doc.as_text() and seen == [b"\x89PNG"]
    plain = asyncio.run(DocumentReader([tmp_path], tmp_path / "dl").read(str(p)))
    assert "scanned page" in plain.as_text()


def test_only_allowed_folders_and_no_links(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "keys.txt"
    secret.write_text("nope")
    inside = tmp_path / "inside"
    inside.mkdir()
    reader = DocumentReader([inside], tmp_path / "dl")
    for bad in (str(secret), str(inside / ".." / "outside" / "keys.txt"), "https://example.com/a.pdf",
                str(inside / "missing.pdf")):
        with pytest.raises(ToolError):
            asyncio.run(reader.read(bad))


def test_word_and_slides_read_through_markitdown(tmp_path):
    pytest.importorskip("markitdown")
    import docx  # python-docx comes with markitdown[docx]
    d = docx.Document()
    d.add_heading("Lab report", 1)
    d.add_paragraph("The truss held 40 N.")
    d.save(tmp_path / "report.docx")
    out = asyncio.run(Registry().run("read_document", {"path": str(tmp_path / "report.docx")},
                                     ToolContext(root=tmp_path, documents=DocumentReader([tmp_path], tmp_path / "dl"))))
    assert not out.is_error and "40 N" in out.content
