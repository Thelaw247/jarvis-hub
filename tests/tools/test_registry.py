"""The tools folder (JARVIS_DESIGN_TOOLS.md §3, §5): every tool is well formed, tiers hold in code, and the voice
brain's list puts rare tools behind tool search."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from jarvis.tools import Registry, ToolContext
from jarvis.tools.registry import TOOLS_DIR, SpecError, parse_tool_md


def ctx(**kw) -> ToolContext:
    return ToolContext(root=Path("."), **kw)


def test_every_tool_folder_is_well_formed_and_says_when_to_use_it():
    reg = Registry()
    assert {"web_search", "web_fetch", "canvas_find", "canvas_read", "read_document", "browse", "research",
            "start_task", "show_page", "recall", "sign_in", "ask_dewet"} <= set(reg.specs)
    for spec in reg.specs.values():
        assert spec.summary and len(spec.summary) <= 160
        if spec.server is None:
            low = spec.description.lower()
            assert "when to use" in low and "when not to use" in low, spec.id
            assert "cost and speed" in low, spec.id  # how long and how much, like Claude's own tool docs
            assert spec.input_schema["type"] == "object"


def test_a_tool_without_when_not_to_use_is_refused(tmp_path):
    folder = tmp_path / "bad_tool"
    folder.mkdir()
    (folder / "TOOL.md").write_text("---\nid: bad_tool\ninput: {type: object}\n---\nDoes things.\nWhen to use: always.\n")
    with pytest.raises(SpecError):
        parse_tool_md(folder)


def test_a_never_tool_is_never_offered(tmp_path):
    folder = tmp_path / "pay_money"
    folder.mkdir()
    (folder / "TOOL.md").write_text("---\nid: pay_money\ntier: never\ninput: {type: object}\n---\nPay.\n"
                                     "When to use: never.\nWhen not to use: always.\n")
    (folder / "handler.py").write_text("async def run(args, ctx):\n    return 'paid'\n")
    reg = Registry([folder])
    assert "pay_money" not in reg.specs


def test_the_voice_list_loads_every_tool_and_defers_only_when_there_are_many(monkeypatch):
    reg = Registry()
    c = ctx(canvas=object(), documents=object(), browser=object(), tasks=object(), memory=object(),
            questions=object())
    tools = reg.voice_tools(c)
    names = [t.get("name") for t in tools]
    # v0.14.0: no tool search with this few tools (it cost a round trip before every "deferred" tool's first use)
    assert not any(str(t.get("type", "")).startswith("tool_search_tool") for t in tools)
    assert not any(t.get("defer_loading") for t in tools)
    assert "web_search" in names and "web_fetch" in names               # Anthropic's own server tools
    assert set(names) >= {"canvas_find", "show_page", "start_task", "recall", "read_document", "browse", "research",
                          "canvas_read", "sign_in"}
    assert "ask_dewet" not in names                                     # tasks only
    cached = [t for t in tools if "cache_control" in t]
    assert len(cached) == 1 and tools[-1] is cached[0]                  # the whole list is cached once

    monkeypatch.setattr(Registry, "DEFER_ABOVE", 3)                     # with many tools, deferral comes back
    tools = reg.voice_tools(c)
    assert tools[0]["type"].startswith("tool_search_tool")             # first, never deferred
    loaded = [t for t in tools if "defer_loading" not in t and "input_schema" in t]
    deferred = [t for t in tools if t.get("defer_loading")]
    assert {t["name"] for t in loaded} >= {"canvas_find", "show_page", "start_task", "recall"}
    assert {t["name"] for t in deferred} >= {"read_document", "browse", "research", "canvas_read"}
    cached = [t for t in tools if "cache_control" in t]
    assert len(cached) == 1 and not cached[0].get("defer_loading")

def test_tools_whose_service_is_missing_are_off_and_say_so():
    reg = Registry()
    c = ctx()  # nothing installed
    assert reg.status(reg.get("canvas_find"), c) == "off"
    names = [t.get("name") for t in reg.voice_tools(c)]
    assert "canvas_find" not in names and "web_search" in names
    out = asyncio.run(reg.run("canvas_find", {"query": "lab 5"}, c))
    assert out.is_error and "switched off or not set up" in out.content


def test_a_signed_out_service_is_asked_again_and_says_what_to_do_if_it_is_still_signed_out():
    """v0.22.1: a raised sign-in flag no longer stops the call (it made "not signed in" permanent); the tool asks
    Canvas again, and if Canvas still wants a sign-in Jarvis is told what to do about it."""
    from jarvis.canvas import SignInNeeded

    class Canvas:
        needs_sign_in = True

        async def find(self, *a, **k):
            self.needs_sign_in = True
            raise SignInNeeded("sign in")

    reg = Registry()
    canvas = Canvas()
    out = asyncio.run(reg.run("canvas_find", {"query": "lab"}, ctx(canvas=canvas)))
    assert out.is_error and "sign in first" in out.content and "Call sign_in with site canvas" in out.content
    assert canvas.needs_sign_in is True


def test_failures_come_back_as_words_never_as_exceptions(tmp_path):
    for name, body in (("boom", "raise RuntimeError('x')"), ("refuse", "raise ToolError('Not that one.')"),
                       ("slow", "import asyncio\n    await asyncio.sleep(5)")):
        folder = tmp_path / name
        folder.mkdir()
        (folder / "TOOL.md").write_text(f"---\nid: {name}\nspeed: instant\ninput: {{type: object}}\n---\nTest.\n"
                                         "When to use: tests.\nWhen not to use: otherwise.\n")
        (folder / "handler.py").write_text(f"from jarvis.tools import ToolError\nasync def run(args, ctx):\n    {body}\n")
    reg = Registry(sorted(tmp_path.iterdir()))
    import jarvis.tools.registry as r
    r.TIMEOUT_S["instant"] = 0.2
    try:
        boom = asyncio.run(reg.run("boom", {}, ctx()))
        refuse = asyncio.run(reg.run("refuse", {}, ctx()))
        slow = asyncio.run(reg.run("slow", {}, ctx()))
    finally:
        r.TIMEOUT_S["instant"] = 3.0
    assert boom.is_error and "RuntimeError" in boom.content and "x" not in boom.content.split("(")[0]
    assert refuse.is_error and refuse.content == "Not that one."
    assert slow.is_error and "too long" in slow.content
    assert asyncio.run(reg.run("nope", {}, ctx())).is_error


def test_show_page_puts_a_web_window_on_the_stage_and_refuses_other_schemes():
    reg = Registry()
    shown = []

    async def publish(t, d):
        shown.append((t, d))
    out = asyncio.run(reg.run("show_page", {"pages": [{"url": "https://canvas.usask.ca/courses/1", "title": "GE 122"}]},
                              ctx(publish=publish)))
    assert not out.is_error and shown and shown[0][0] == "window.push"
    window = shown[0][1]
    assert window["type"] == "web" and window["data"]["pages"][0]["url"].startswith("https://")
    from tests.test_contracts import validator  # noqa: PLC0415
    assert list(validator("window").iter_errors(window)) == []
    bad = asyncio.run(reg.run("show_page", {"pages": [{"url": "file:///C:/secrets.txt", "title": "x"}]}, ctx()))
    assert bad.is_error


def test_reach_rows_match_the_contract():
    from tests.test_contracts import validator  # noqa: PLC0415
    reg = Registry()
    rows = reg.reach_rows(ctx())
    reach = {"tools": rows, "folders": [], "apps": [], "caps": {"task_usd": 1, "day_usd": 5, "spent_today_usd": 0}}
    assert list(validator("reach").iter_errors(reach)) == []


def test_the_index_names_every_ability_in_one_line_each():
    reg = Registry()
    text = reg.index_text()
    assert all(f"- {tid}:" in text for tid in reg.specs)
    assert len(text) < 3000  # ~600-700 tokens in the cached prefix
    assert TOOLS_DIR.name == "tools"
