"""Canvas through his session (TOOLS §7): search across kinds, open an item, GET only, sign-in noticed."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from jarvis.canvas import CanvasClient, SignInNeeded
from jarvis.canvas.client import Response
from jarvis.tools import Registry, ToolContext

BASE = "https://canvas.usask.ca"
COURSES = [{"id": 101, "course_code": "GE122.03", "name": "GE 122 Engineering Mechanics"},
           {"id": 202, "course_code": "CHEM 142", "name": "CHEM 142 General Chemistry"}]
DATA = {
    "/api/v1/courses": COURSES,
    "/api/v1/courses/101/assignments": [
        {"id": 5, "name": "Lab 5: Trusses", "description": "<p>Build the <b>truss</b>. Room <a href='x'>1B71</a>.</p>",
         "due_at": "2026-11-20T23:59:00Z", "html_url": f"{BASE}/courses/101/assignments/5"},
        {"id": 6, "name": "Problem set 7", "description": "Friction", "due_at": None,
         "html_url": f"{BASE}/courses/101/assignments/6"}],
    "/api/v1/courses/101/pages": [{"url": "formula-sheet", "title": "Formula sheet", "updated_at": "2026-11-01T00:00:00Z"}],
    "/api/v1/courses/101/files": [{"id": 77, "display_name": "Midterm 2 formula sheet.pdf", "filename": "f.pdf"}],
    "/api/v1/courses/101/modules": [{"id": 9, "name": "Week 10", "items": [
        {"title": "Lecture 22 slides", "type": "File", "html_url": f"{BASE}/courses/101/modules/items/1"}]}],
    "/api/v1/courses/101/discussion_topics": [],
    "/api/v1/courses/202/assignments": [{"id": 8, "name": "Lab 4 worksheet", "description": "Titration",
                                         "html_url": f"{BASE}/courses/202/assignments/8"}],
    "/api/v1/announcements": [{"id": 3, "title": "Midterm room change", "message": "<p>The midterm is in Thorvaldson 159.</p>",
                               "posted_at": "2026-11-10T15:00:00Z", "html_url": f"{BASE}/courses/101/discussion_topics/3"}],
    "/api/v1/courses/101/assignments/5": {"id": 5, "name": "Lab 5: Trusses", "description": "<p>Build the truss.</p>",
                                          "due_at": "2026-11-20T23:59:00Z", "points_possible": 10,
                                          "submission_types": ["online_upload"], "html_url": f"{BASE}/courses/101/assignments/5"},
    "/api/v1/files/77": {"id": 77, "display_name": "Midterm 2 formula sheet.pdf", "filename": "formula.pdf",
                         "size": 2048, "url": f"{BASE}/files/77/download"},
    "/files/77/download": b"%PDF-1.4 fake",
}


def make(signed_in: bool = True, seen: list | None = None, tmp: Path | None = None) -> CanvasClient:
    async def fetch(url: str) -> Response:
        if seen is not None:
            seen.append(url)
        if not signed_in:
            return Response(200, {}, b"<html>login</html>", f"{BASE}/login/saml")
        path = url.replace(BASE, "").split("?")[0]
        body = DATA.get(path, [] if path.endswith(("pages", "files", "modules", "discussion_topics", "assignments"))
                        else None)
        if body is None:
            return Response(404, {}, b"{}", url)
        raw = body if isinstance(body, bytes) else ("while(1);" + json.dumps(body)).encode()
        return Response(200, {}, raw, url)
    return CanvasClient(fetch, downloads=tmp)


def test_find_ranks_across_kinds_and_courses():
    hits = asyncio.run(make().find("lab 5 truss"))
    assert hits[0].title == "Lab 5: Trusses" and hits[0].course == "GE 122" and hits[0].due
    assert "truss" in hits[0].snippet.lower()
    room = asyncio.run(make().find("midterm room"))
    assert room[0].kind == "announcement" and "Thorvaldson" in room[0].snippet
    sheet = asyncio.run(make().find("formula sheet", course="GE 122"))
    assert {h.kind for h in sheet[:2]} == {"page", "file"}
    chem = asyncio.run(make().find("worksheet", course="chem142"))
    assert chem[0].course == "CHEM 142"


def test_lists_are_cached_so_a_second_search_is_instant():
    seen: list[str] = []
    client = make(seen=seen)
    asyncio.run(client.find("lab"))
    n = len(seen)
    asyncio.run(client.find("midterm"))
    assert len(seen) == n


def test_read_an_assignment_and_download_a_file(tmp_path):
    client = make(tmp=tmp_path)
    item = asyncio.run(client.read(f"{BASE}/courses/101/assignments/5"))
    assert "Build the truss" in item.text() and "Points: 10" in item.text() and item.due
    f = asyncio.run(client.read(f"{BASE}/courses/101/files/77"))
    assert f.file_path is not None and f.file_path.read_bytes().startswith(b"%PDF") and tmp_path in f.file_path.parents


def test_only_canvas_links_and_sign_in_is_noticed():
    with pytest.raises(Exception, match="Only Canvas links"):
        asyncio.run(make().get("https://evil.example/api/v1/courses"))
    client = make(signed_in=False)
    with pytest.raises(SignInNeeded):
        asyncio.run(client.find("lab"))
    assert client.needs_sign_in
    # through the tool: Jarvis is told to tell him once, not to retry
    out = asyncio.run(Registry().run("canvas_find", {"query": "lab"}, ToolContext(root=Path("."), canvas=client)))
    assert out.is_error and "sign in" in out.content.lower()


def test_the_client_has_no_way_to_write():
    client = make()
    assert not any(hasattr(client, m) for m in ("post", "put", "delete", "submit"))
