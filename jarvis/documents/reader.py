"""Read documents for Jarvis: PDFs (PyMuPDF), Word/Excel/PowerPoint/HTML/EPUB (MarkItDown), text, and images or
scanned pages (Claude's vision, when a vision callable is given). JARVIS_DESIGN_TOOLS.md §8.

Long documents never flood the prompt: with a question, the pages that match it come back (plus an outline);
without one, the first pages up to a size limit, and a note saying how to ask for more.
Only files inside his allowed folders or Jarvis's downloads folder can be read (REACH §2).
"""
from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from jarvis.tools.base import ToolError

TEXT_SUFFIXES = {".txt", ".md", ".csv", ".json", ".py", ".log", ".tex", ".xml", ".yaml", ".yml", ".ini", ".cfg"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
MAX_BYTES = 100 * 1024 * 1024
BUDGET = 30_000          # characters returned at most (about 7–8k tokens)
MAX_VISION_PAGES = 6
STOP = {"the", "a", "an", "of", "in", "on", "to", "and", "is", "what", "does", "for", "it", "with", "about", "my"}

Vision = Callable[[bytes, str], Awaitable[str]]   # (png bytes, prompt) -> text


@dataclass
class Doc:
    path: Path
    title: str
    page_count: int
    pages: list[tuple[int, str]] = field(default_factory=list)
    outline: list[str] = field(default_factory=list)
    note: str = ""

    @property
    def pages_returned(self) -> int:
        return len(self.pages)

    def as_text(self) -> str:
        head = f"# {self.title} ({self.page_count} page{'s' if self.page_count != 1 else ''})"
        parts = [head]
        if self.outline and self.pages_returned < self.page_count:
            parts.append("Outline: " + " · ".join(self.outline[:40]))
        for n, text in self.pages:
            parts.append(f"--- page {n} ---\n{text.strip()}" if self.page_count > 1 else text.strip())
        if self.note:
            parts.append(f"[{self.note}]")
        return "\n\n".join(parts)


def parse_pages(spec: str | None, count: int) -> list[int] | None:
    if not spec:
        return None
    out: list[int] = []
    for part in re.split(r"[,\s]+", spec.strip()):
        if not part:
            continue
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", part)
        if not m:
            raise ToolError(f"Pages should look like '3-5' or '7', not {spec!r}.")
        a, b = int(m.group(1)), int(m.group(2) or m.group(1))
        out += [n for n in range(min(a, b), max(a, b) + 1) if 1 <= n <= count]
    if not out:
        raise ToolError(f"The document has {count} page(s); none of {spec!r} exist.")
    return sorted(set(out))


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP and len(w) > 1]


def pick_pages(all_pages: Sequence[tuple[int, str]], question: str | None, budget: int = BUDGET
               ) -> tuple[list[tuple[int, str]], str]:
    """The pages to return: everything if it fits; the best matches for a question; otherwise the first ones."""
    total = sum(len(t) for _, t in all_pages)
    if total <= budget:
        return list(all_pages), ""
    if question:
        qw = set(_words(question))
        scored = []
        for n, t in all_pages:
            tw = _words(t)
            hits = sum(1 for w in tw if w in qw)
            if hits:
                scored.append((hits / (1 + len(tw) ** 0.5), n, t))
        scored.sort(reverse=True)
        chosen, size = [], 0
        for _, n, t in scored:
            if size + len(t) > budget and chosen:
                break
            chosen.append((n, t))
            size += len(t)
        if chosen:
            chosen.sort()
            return chosen, (f"Showing the {len(chosen)} pages that match the question; ask for other pages with "
                            "`pages`.")
    chosen, size = [], 0
    for n, t in all_pages:
        if size + len(t) > budget and chosen:
            break
        chosen.append((n, t))
        size += len(t)
    return chosen, f"Showing pages 1–{chosen[-1][0]}; ask for more with `pages`, or pass a `question`."


def _heading(text: str) -> str:
    for line in text.splitlines():
        line = line.strip(" #*\t")
        if 3 <= len(line) <= 80:
            return line
    return ""


class DocumentReader:
    def __init__(self, allowed_roots: Sequence[Path], downloads: Path, *, vision: Vision | None = None) -> None:
        self.roots = [Path(r).resolve() for r in allowed_roots] + [Path(downloads).resolve()]
        self.vision = vision

    def resolve(self, path: str) -> Path:
        if path.startswith(("http://", "https://")):
            raise ToolError("That's a link: use web_fetch for an online document (or canvas_read for Canvas).")
        p = Path(path).expanduser()
        try:
            p = p.resolve(strict=True)
        except (FileNotFoundError, OSError) as e:
            raise ToolError(f"There's no file at {path}.") from e
        if not any(p == r or r in p.parents for r in self.roots):
            raise ToolError("That file is outside the folders Jarvis may read (Controls › Reach › Folders).")
        if not p.is_file():
            raise ToolError(f"{path} is a folder, not a file.")
        if p.stat().st_size > MAX_BYTES:
            raise ToolError("That file is over 100 MB; too big to read here.")
        return p

    async def read(self, path: str, *, pages: str | None = None, question: str | None = None) -> Doc:
        p = self.resolve(path)
        suffix = p.suffix.lower()
        if suffix == ".pdf":
            doc = await asyncio.to_thread(self._pdf, p)
        elif suffix in IMAGE_SUFFIXES:
            doc = await self._image(p, question)
        elif suffix in TEXT_SUFFIXES:
            text = p.read_text(encoding="utf-8", errors="replace")
            doc = Doc(p, p.name, 1, [(1, text)])
        else:
            doc = await asyncio.to_thread(self._markitdown, p)
        await self._scans(p, doc)
        wanted = parse_pages(pages, doc.page_count)
        if wanted is not None:
            doc.pages = [(n, t) for n, t in doc.pages if n in wanted]
            doc.pages, note = pick_pages(doc.pages, question)
        else:
            doc.pages, note = pick_pages(doc.pages, question)
        doc.note = " ".join(x for x in (doc.note, note) if x)
        return doc

    # ------------------------------------------------------------------ formats
    def _pdf(self, p: Path) -> Doc:
        import pymupdf as fitz  # noqa: PLC0415

        with fitz.open(p) as pdf:
            title = (pdf.metadata or {}).get("title") or p.name
            pages, outline = [], []
            toc = pdf.get_toc(simple=True) or []
            outline = [f"{t} (p{pg})" for _, t, pg in toc[:60]]
            for i, page in enumerate(pdf, start=1):
                text = page.get_text("text") or ""
                if len(text.strip()) < 25 and page.get_images():
                    text = "\0scan"
                pages.append((i, text))
            if not outline:
                outline = [f"p{n}: {h}" for n, t in pages if (h := _heading(t)) and t != "\0scan"][:40]
            return Doc(p, title, len(pages), pages, outline)

    def _markitdown(self, p: Path) -> Doc:
        try:
            from markitdown import MarkItDown  # noqa: PLC0415
        except ImportError as e:
            raise ToolError("Word, Excel and PowerPoint reading isn't installed yet: run setup-tools.bat on "
                            "Laptop B.") from e
        text = MarkItDown(enable_plugins=False).convert(str(p)).text_content or ""
        parts = re.split(r"<!-- Slide number: (\d+) -->", text)
        if len(parts) > 2:  # PowerPoint: one page per slide
            pages = [(int(parts[i]), parts[i + 1]) for i in range(1, len(parts) - 1, 2)]
        else:
            sheets = re.split(r"(?m)^## (?=\S)", text)
            pages = [(i + 1, ("## " if i else "") + s) for i, s in enumerate(sheets) if s.strip()] or [(1, text)]
        outline = [f"{n}: {h}" for n, t in pages if (h := _heading(t))][:40]
        return Doc(p, p.name, len(pages), pages, outline if len(pages) > 1 else [])

    async def _image(self, p: Path, question: str | None) -> Doc:
        if self.vision is None:
            raise ToolError("Reading images needs the vision step, which isn't connected.")
        data = p.read_bytes()
        prompt = "Transcribe all text in this image exactly (keep tables), then describe any figure in one line."
        if question:
            prompt += f" He wants to know: {question}"
        return Doc(p, p.name, 1, [(1, await self.vision(data, prompt))])

    async def _scans(self, p: Path, doc: Doc) -> None:
        scans = [n for n, t in doc.pages if t == "\0scan"]
        if not scans:
            return
        if self.vision is None or p.suffix.lower() != ".pdf":
            doc.pages = [(n, "[scanned page: no text layer]" if t == "\0scan" else t) for n, t in doc.pages]
            return
        import pymupdf as fitz  # noqa: PLC0415

        done: dict[int, str] = {}
        with fitz.open(p) as pdf:
            for n in scans[:MAX_VISION_PAGES]:
                png = pdf[n - 1].get_pixmap(dpi=150).tobytes("png")
                done[n] = await self.vision(png, "Transcribe all text on this page exactly, keeping tables and "
                                                  "equations; describe each figure in one line.")
        doc.pages = [(n, done.get(n, "[scanned page: ask for it by number to read it]") if t == "\0scan" else t)
                     for n, t in doc.pages]
