"""v0.19.1: his report that on Laptop B "nothing lands" and no tool had ever run. Tool history now survives a restart,
refusals leave a reason, and one page says what works on a laptop without showing a key."""
import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

from jarvis.tools.base import Result, ToolError
from jarvis.tools.registry import Registry


def load(path):
    spec = importlib.util.spec_from_file_location(Path(path).stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ctx(**have):
    return SimpleNamespace(has=lambda need: need in have, publish=None, show=None, **have)


def test_what_ran_and_what_was_refused_survives_a_restart(tmp_path):
    store = tmp_path / "data" / "tool_use.json"
    reg = Registry()
    reg.remember(store)

    async def ok(args, c): return Result("Two classes.")
    async def bad(args, c): raise ToolError("There's no Composio key yet. He adds it in Controls.")

    reg.handlers["school"], reg.handlers["calendar"] = ok, bad
    assert asyncio.run(reg.run("school", {}, ctx(classes=object()))).is_error is False
    assert asyncio.run(reg.run("calendar", {}, ctx(calendar=object()))).is_error is True
    assert asyncio.run(reg.run("canvas_find", {"query": "x"}, ctx())).is_error is True          # not set up: refused before it runs
    again = Registry()
    again.remember(store)                                                                         # "the core restarted"
    assert again.last_used["school"] and again.use["school"] == {"runs": 1, "fails": 0, "last_used": again.last_used["school"]}
    assert again.use["calendar"]["fails"] == 1 and "no Composio key yet" in again.use["calendar"]["last_error"]
    assert "canvas_find" not in again.last_used and "not set up here (missing: canvas)" in again.use["canvas_find"]["last_error"]
    rows = {r["id"]: r for r in again.reach_rows(ctx(classes=object()))}
    assert rows["school"]["last_used"] == again.last_used["school"] and rows["canvas-find"]["last_used"] is None
    assert "Two classes" not in store.read_text(encoding="utf-8")                                 # never a result, only that it ran
    asyncio.run(again.run("calendar", {}, ctx(calendar=SimpleNamespace())))                        # a broken file never stops a tool
    store.write_text("{not json", encoding="utf-8")
    Registry().remember(store)


def test_the_report_says_what_works_and_never_shows_a_key(tmp_path):
    doctor = load("tools/doctor.py")
    code, root = tmp_path / "Jarvis", tmp_path / "data-root"
    (code / "tools").mkdir(parents=True)
    (code / "VERSION").write_text("0.19.1\n")
    (root / "logs").mkdir(parents=True)
    (root / "data").mkdir()
    (root / "data" / "tool_use.json").write_text(json.dumps({"calendar": {"runs": 2, "fails": 2, "last_used": "2026-11-22T17:05:00",
                                                                           "last_error": "2026-11-22T17:05:00 There's no Composio key yet"}}))
    (root / "logs" / "core.jsonl").write_text("\n".join(json.dumps(r) for r in [
        {"ts": "2026-11-22T17:04:59.100", "level": "info", "event": "http.request"},
        {"ts": "2026-11-22T17:05:00.100", "level": "info", "event": "tool.ran", "tool": "calendar", "ms": 12.5, "error": True},
        {"ts": "2026-11-22T17:05:02.000", "level": "warning", "event": "tool.failed", "tool": "sign_in", "error": "FileNotFoundError"}]) + "\nnot json\n")

    def get(base, path, session):
        assert base == "http://127.0.0.1:8770"
        if path == "/healthz": return 200, {"ok": True, "version": "0.19.1"}
        if path == "/api/state":
            return 200, {"reach": {"tools": [{"id": "calendar", "status": "connected", "last_used": None, "on": True},
                                             {"id": "canvas-find", "status": "needs_sign_in", "last_used": None, "on": True}]},
                         "metrics": {"connectors": [{"name": "Google Calendar", "status": "off", "note": "No key"}]}, "branches": [1, 2], "day": {"items": []}}
        return 200, {"providers": [{"id": "anthropic", "name": "Anthropic", "status": "ok", "live": True, "slots": {"live": {"last4": "9xQ2"}}},
                                   {"id": "composio", "name": "Composio", "status": "missing", "live": False, "token": "sk-should-never-show"}]}

    text = doctor.report(code, root, {"COMPUTERNAME": "LAPTOP-B", "JARVIS_CORE_SESSION": "sess-abc123"}, get=get)
    assert "version 0.19.1" in text and "paired: yes" in text and "Core on this laptop (127.0.0.1:8770): answers" in text
    assert "needs_sign_in  canvas-find · last used never" in text and "off    Google Calendar · No key" in text
    assert "Anthropic: status=ok, live=True" in text and "Composio: status=missing, live=False" in text
    assert "calendar: ran 2, failed 2" in text and "last problem: 2026-11-22T17:05:00 There's no Composio key yet" in text
    assert "tool.ran tool=calendar error=True ms=12.5" in text and "tool.failed tool=sign_in error=FileNotFoundError" in text
    assert "http.request" not in text
    for secret in ("9xQ2", "sk-should-never-show", "sess-abc123"):
        assert secret not in text
    down = doctor.report(code, tmp_path / "nowhere", {}, get=lambda *a: (None, "URLError: refused"))
    assert "NOT ANSWERING" in down and "MISSING" in down and "paired: NO" in down
    assert doctor.where_to_write(code, {"OneDrive": str(tmp_path / "none"), "COMPUTERNAME": "LAPTOP B!"}) == tmp_path / "reports" / "jarvis-report-laptop-b-.txt"


def test_jarvis_is_told_not_to_claim_what_he_did_not_do():
    from jarvis.tools.voice import ROUTING

    assert "Never say you checked, looked, opened or tried something unless a tool result" in ROUTING


def test_the_report_file_is_a_plain_windows_file():
    raw = Path("Jarvis report.bat").read_bytes()
    raw.decode("ascii")
    assert b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"") and b"tools\\doctor.py" in raw


def test_a_sign_in_flag_never_stops_jarvis_from_finding_out_he_has_signed_in(tmp_path):
    """Laptop B, 2026-11-22: after Canvas asked for a sign-in once, every later call was refused before it ran, so
    Jarvis kept saying "not signed in" although he was."""
    reg = Registry()
    canvas = SimpleNamespace(needs_sign_in=True)
    calls = []

    async def find(args, c):
        calls.append(args)
        return Result("Three things due.")          # Canvas answers: he is signed in now

    reg.handlers["canvas_find"] = find
    assert reg.status(reg.specs["canvas_find"], ctx(canvas=canvas)) == "needs_sign_in"     # what the hub showed
    out = asyncio.run(reg.run("canvas_find", {"query": "due"}, ctx(canvas=canvas)))
    assert out.is_error is False and out.content == "Three things due." and calls == [{"query": "due"}]
    assert canvas.needs_sign_in is False
