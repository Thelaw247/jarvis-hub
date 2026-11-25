"""Canvas through De Wet's own session: the JSON endpoints the Canvas website itself calls, GET only.

No token (USask doesn't issue students one, RUNTIME §5a): requests carry the Jarvis browser profile's cookies. Only
GETs to the Canvas host are possible from here; there is no code path that posts, puts or deletes.

``find`` searches every active course's assignments, announcements, modules and items, pages, files, discussions
and syllabus, ranks by how well titles and text match the words asked, then by recency (JARVIS_DESIGN_TOOLS.md §7).
Lists are cached for ten minutes per course, so repeat lookups are instant.
"""
from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .html import html_to_text

CANVAS = "https://canvas.usask.ca"
CACHE_S = 600
PER_PAGE = 100
MAX_PAGES = 5
KINDS = ("assignment", "announcement", "module_item", "page", "file", "discussion", "syllabus")
STOP = {"the", "a", "an", "for", "of", "in", "on", "to", "my", "and", "is", "what", "when", "where", "does", "do",
        "about", "with", "this", "that", "it", "be", "are", "find", "show", "me"}


class CanvasError(Exception):
    pass


class SignInNeeded(CanvasError):
    pass


@dataclass
class Response:
    status: int
    headers: dict[str, str]
    body: bytes
    url: str = ""

    def json(self) -> Any:
        import json  # noqa: PLC0415

        return json.loads(self.body.decode("utf-8", "replace"))


Fetch = Callable[[str], Awaitable[Response]]


@dataclass
class Hit:
    course: str
    kind: str
    title: str
    link: str
    snippet: str = ""
    due: str | None = None
    when: str | None = None
    score: float = 0.0

    def line(self) -> str:
        bits = [f"[{self.course}] {self.kind}: {self.title}"]
        if self.due:
            bits.append(f"due {self.due}")
        elif self.when:
            bits.append(self.when[:10])
        if self.snippet:
            bits.append(f"“{self.snippet}”")
        return " · ".join(bits) + f" · {self.link}"


@dataclass
class Item:
    course: str
    kind: str
    title: str
    link: str
    body: str = ""
    due: str | None = None
    extra: list[str] = field(default_factory=list)
    file_path: Path | None = None

    def header(self) -> str:
        due = f" · due {self.due}" if self.due else ""
        return f"[{self.course}] {self.kind}: {self.title}{due}\n{self.link}"

    def text(self) -> str:
        parts = [self.header()]
        if self.body:
            parts.append(self.body)
        parts += self.extra
        return "\n\n".join(parts)


def words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP and (len(w) > 1 or w.isdigit())]


def score(query_words: list[str], title: str, body: str = "") -> float:
    if not query_words:
        return 0.0
    t, b = set(words(title)), set(words(body))
    hits = sum(2.0 if w in t else (0.7 if w in b else 0.0) for w in query_words)
    phrase = " ".join(query_words)
    if phrase and phrase in " ".join(words(title)):
        hits += 2.0
    return hits / (2.0 * len(query_words))


def snippet(body: str, query_words: list[str], width: int = 140) -> str:
    text = " ".join(body.split())
    low = text.lower()
    pos = min((low.find(w) for w in query_words if low.find(w) >= 0), default=-1)
    if pos < 0:
        return text[:width] + ("…" if len(text) > width else "")
    start = max(0, pos - width // 3)
    out = text[start:start + width]
    return ("…" if start else "") + out + ("…" if start + width < len(text) else "")


def local_time(iso: str | None) -> str | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
    except ValueError:
        return iso
    hour = dt.hour % 12 or 12  # no %-d / %-I: Windows' strftime doesn't have them
    return f"{dt:%a %b} {dt.day} {hour}:{dt:%M} {'am' if dt.hour < 12 else 'pm'}"


class CanvasClient:
    def __init__(self, fetch: Fetch, *, base: str = CANVAS, downloads: Path | None = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.fetch = fetch
        self.base = base.rstrip("/")
        self.host = urlparse(self.base).hostname
        self.downloads = downloads
        self.clock = clock
        self._cache: dict[str, tuple[float, Any]] = {}
        self.needs_sign_in = False

    # ------------------------------------------------------------------ GET only
    def _url(self, path: str) -> str:
        if path.startswith("http"):
            p = urlparse(path)
            if p.hostname != self.host:
                raise CanvasError("Only Canvas links can be read here.")
            return path
        return self.base + (path if path.startswith("/") else "/" + path)

    async def get(self, path: str) -> Response:
        resp = await self.fetch(self._url(path))
        if resp.status in (401, 403) or "/login" in (resp.url or ""):
            self.needs_sign_in = True
            raise SignInNeeded("Canvas wants De Wet to sign in again (sign_in: canvas).")
        if resp.status >= 400:
            raise CanvasError(f"Canvas answered {resp.status} for that.")
        self.needs_sign_in = False
        return resp

    async def get_json(self, path: str) -> Any:
        resp = await self.get(path)
        body = resp.body.lstrip()
        if body.startswith(b"while(1);"):  # Canvas's JSON hijacking guard on session requests
            body = body[len(b"while(1);"):]
        import json  # noqa: PLC0415

        return json.loads(body.decode("utf-8", "replace"))

    async def get_all(self, path: str) -> list[Any]:
        sep = "&" if "?" in path else "?"
        url: str | None = f"{path}{sep}per_page={PER_PAGE}"
        out: list[Any] = []
        for _ in range(MAX_PAGES):
            if url is None:
                break
            resp = await self.get(url)
            data = await self._decode(resp)
            if isinstance(data, list):
                out += data
            else:
                return [data]
            url = _next_link(resp.headers.get("link") or resp.headers.get("Link") or "")
        return out

    async def _decode(self, resp: Response) -> Any:
        body = resp.body.lstrip()
        if body.startswith(b"while(1);"):
            body = body[len(b"while(1);"):]
        import json  # noqa: PLC0415

        return json.loads(body.decode("utf-8", "replace"))

    async def cached(self, key: str, make: Callable[[], Awaitable[Any]]) -> Any:
        hit = self._cache.get(key)
        if hit and self.clock() - hit[0] < CACHE_S:
            return hit[1]
        try:
            value = await make()
        except SignInNeeded:
            raise
        except CanvasError:  # a part of the course that's switched off (404/403): remember that too
            value = []
        self._cache[key] = (self.clock(), value)
        return value

    # ------------------------------------------------------------------ courses
    async def courses(self) -> list[dict]:
        rows = await self.cached("courses", lambda: self.get_all(
            "/api/v1/courses?enrollment_state=active&include[]=term"))
        return [c for c in rows if isinstance(c, dict) and c.get("id") and not c.get("access_restricted_by_date")]

    @staticmethod
    def code(course: dict) -> str:
        code = course.get("course_code") or course.get("name") or str(course.get("id"))
        m = re.match(r"([A-Z]{2,5})\s*-?\s*(\d{3})", code.upper())
        return f"{m.group(1)} {m.group(2)}" if m else code

    def _match_course(self, courses: list[dict], wanted: str | None) -> list[dict]:
        if not wanted:
            return courses
        w = re.sub(r"[^a-z0-9]", "", wanted.lower())
        pick = [c for c in courses if w in re.sub(r"[^a-z0-9]", "", (self.code(c) + (c.get("name") or "")).lower())]
        return pick or courses

    # ------------------------------------------------------------------ find
    async def _collect(self, course: dict, kinds: tuple[str, ...]) -> list[Hit]:
        cid, code = course["id"], self.code(course)
        base = f"/api/v1/courses/{cid}"
        jobs: dict[str, Awaitable[Any]] = {}
        if "assignment" in kinds:
            jobs["assignment"] = self.cached(f"{cid}:a", lambda: self.get_all(f"{base}/assignments?order_by=due_at"))
        if "announcement" in kinds:
            since = (datetime.now(UTC) - timedelta(days=150)).strftime("%Y-%m-%d")
            jobs["announcement"] = self.cached(f"{cid}:n", lambda: self.get_all(
                f"/api/v1/announcements?context_codes[]=course_{cid}&start_date={since}"))
        if "module_item" in kinds:
            jobs["module_item"] = self.cached(f"{cid}:m", lambda: self.get_all(f"{base}/modules?include[]=items"))
        if "page" in kinds:
            jobs["page"] = self.cached(f"{cid}:p", lambda: self.get_all(f"{base}/pages?sort=updated_at&order=desc"))
        if "file" in kinds:
            jobs["file"] = self.cached(f"{cid}:f", lambda: self.get_all(f"{base}/files?sort=updated_at&order=desc"))
        if "discussion" in kinds:
            jobs["discussion"] = self.cached(f"{cid}:d", lambda: self.get_all(f"{base}/discussion_topics"))
        if "syllabus" in kinds:
            jobs["syllabus"] = self.cached(f"{cid}:s", lambda: self.get_json(f"{base}?include[]=syllabus_body"))
        names = list(jobs)
        results = await asyncio.gather(*jobs.values(), return_exceptions=True)
        hits: list[Hit] = []
        for kind, rows in zip(names, results, strict=True):
            if isinstance(rows, SignInNeeded):
                raise rows
            if isinstance(rows, Exception):
                continue  # a tab the course has switched off (403/404): skip it
            hits += self._hits(code, cid, kind, rows)
        return hits

    def _hits(self, code: str, cid: Any, kind: str, rows: Any) -> list[Hit]:
        out: list[Hit] = []
        if kind == "syllabus":
            body = html_to_text((rows or {}).get("syllabus_body") or "")
            if body:
                out.append(Hit(code, "syllabus", f"{code} syllabus", f"{self.base}/courses/{cid}/assignments/syllabus",
                               snippet="", when=None))
                out[-1].snippet = body  # full text for scoring; trimmed in find
            return out
        for r in rows if isinstance(rows, list) else []:
            if not isinstance(r, dict):
                continue
            if kind == "module_item":
                for it in r.get("items") or []:
                    out.append(Hit(code, "module_item", f"{it.get('title', '')} (module: {r.get('name', '')})",
                                   it.get("html_url") or f"{self.base}/courses/{cid}/modules", snippet=it.get("type", "")))
                continue
            title = r.get("name") or r.get("title") or r.get("display_name") or r.get("filename") or ""
            body = html_to_text(r.get("description") or r.get("message") or r.get("body") or "")
            link = r.get("html_url") or r.get("url") or ""
            if kind == "page" and not link:
                link = f"{self.base}/courses/{cid}/pages/{r.get('url', '')}"
            if kind == "file":
                link = f"{self.base}/courses/{cid}/files/{r.get('id')}"
            out.append(Hit(code, kind, title, link, snippet=body, due=local_time(r.get("due_at")),
                           when=r.get("posted_at") or r.get("updated_at") or r.get("created_at")))
        return out

    async def find(self, query: str, *, course: str | None = None, kinds: list[str] | None = None,
                   limit: int = 10) -> list[Hit]:
        wanted = tuple(k for k in (kinds or KINDS) if k in KINDS) or KINDS
        courses = self._match_course(await self.courses(), course)
        batches = await asyncio.gather(*(self._collect(c, wanted) for c in courses), return_exceptions=True)
        hits: list[Hit] = []
        for b in batches:
            if isinstance(b, SignInNeeded):
                raise b
            if isinstance(b, list):
                hits += b
        qw = words(query)
        for h in hits:
            h.score = score(qw, h.title, h.snippet)
            if course and h.course and re.sub(r"\W", "", course.lower()) in re.sub(r"\W", "", h.course.lower()):
                h.score += 0.05
        ranked = sorted((h for h in hits if h.score > 0.2), key=lambda h: (-h.score, -(_ts(h.when) or 0)))
        for h in ranked:
            h.snippet = snippet(h.snippet, qw) if h.kind not in ("module_item",) else h.snippet
        return ranked[:limit]

    # ------------------------------------------------------------------ read one item
    async def read(self, link: str) -> Item:
        path = urlparse(link).path if link.startswith("http") else link
        path = path.replace("/api/v1", "")
        m = re.match(r"/courses/(\d+)/(assignments|pages|discussion_topics|announcements|files|modules)/?([^/?#]*)", path)
        if not m:
            raise CanvasError("That doesn't look like a Canvas item link (from canvas_find).")
        cid, kind, ident = m.group(1), m.group(2), m.group(3)
        code = next((self.code(c) for c in await self.courses() if str(c["id"]) == cid), f"course {cid}")
        api = f"/api/v1/courses/{cid}"
        if kind == "assignments" and ident == "syllabus":
            data = await self.get_json(f"{api}?include[]=syllabus_body")
            return Item(code, "syllabus", f"{code} syllabus", link, html_to_text(data.get("syllabus_body") or ""))
        if kind == "assignments":
            a = await self.get_json(f"{api}/assignments/{ident}")
            extra = []
            if a.get("points_possible") is not None:
                extra.append(f"Points: {a['points_possible']}")
            if a.get("submission_types"):
                extra.append("Submit by: " + ", ".join(a["submission_types"]))
            return Item(code, "assignment", a.get("name", ""), a.get("html_url", link),
                        html_to_text(a.get("description") or ""), due=local_time(a.get("due_at")), extra=extra)
        if kind == "pages":
            p = await self.get_json(f"{api}/pages/{ident}")
            return Item(code, "page", p.get("title", ""), p.get("html_url", link), html_to_text(p.get("body") or ""))
        if kind in ("discussion_topics", "announcements"):
            d = await self.get_json(f"{api}/discussion_topics/{ident}")
            return Item(code, "announcement" if d.get("is_announcement") else "discussion", d.get("title", ""),
                        d.get("html_url", link), html_to_text(d.get("message") or ""))
        if kind == "modules":
            mods = await self.get_all(f"{api}/modules?include[]=items")
            wanted = [x for x in mods if not ident or str(x.get("id")) == ident]
            lines = []
            for mod in wanted:
                lines.append(f"## {mod.get('name', '')}")
                lines += [f"- {it.get('title', '')} ({it.get('type', '')}) {it.get('html_url', '')}"
                          for it in mod.get("items") or []]
            return Item(code, "modules", wanted[0].get("name", "Modules") if len(wanted) == 1 else "Modules", link,
                        "\n".join(lines))
        # files: metadata, then the bytes into Jarvis's downloads folder (read_document reads it next)
        f = await self.get_json(f"/api/v1/files/{ident}")
        item = Item(code, "file", f.get("display_name") or f.get("filename", ""), link,
                    extra=[f"Size: {round((f.get('size') or 0) / 1024)} KB, updated {(f.get('updated_at') or '')[:10]}"])
        if self.downloads is not None and f.get("url"):
            resp = await self.fetch(f["url"])
            if resp.status < 400 and resp.body:
                self.downloads.mkdir(parents=True, exist_ok=True)
                safe = re.sub(r"[^\w.\- ]", "_", f.get("filename") or f"file-{ident}")[:120]
                path = self.downloads / f"canvas-{ident}-{safe}"
                path.write_bytes(resp.body)
                item.file_path = path
        return item


def _next_link(header: str) -> str | None:
    for part in header.split(","):
        if 'rel="next"' in part:
            m = re.search(r"<([^>]+)>", part)
            if m:
                return m.group(1)
    return None


def _ts(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def playwright_fetch(browser: Any) -> Fetch:
    """GETs through the Jarvis browser's own request context, so the session cookies go with them."""
    async def fetch(url: str) -> Response:
        ctx = await browser.context()
        r = await ctx.request.get(url, headers={"Accept": "application/json+canvas-string-ids, application/json"},
                                  max_redirects=5, timeout=20_000)
        return Response(r.status, dict(r.headers), await r.body(), r.url)
    return fetch
