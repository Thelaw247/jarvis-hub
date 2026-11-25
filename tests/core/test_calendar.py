"""v0.14.0: Jarvis can read his Google Calendar (through Composio), so a schedule question doesn't go to Canvas."""
import asyncio
import json
from datetime import date, timedelta, timezone

import httpx
import pytest

from jarvis.reach.calendar import CalendarClient, CalendarError, NotConnected, parse_events, which_day
from jarvis.secrets.client import KeyedClient
from jarvis.tools.base import ToolContext
from jarvis.tools.registry import default_registry

CST = timezone(timedelta(hours=-6), "CST")
THU = date(2026, 11, 19)


class Keys:
    def __init__(self, key="ck_test"):
        self.client = KeyedClient("composio")
        if key:
            self.client.load(key)
        self.manager = self

    def __getattr__(self, name):
        raise AttributeError(name)


class Manager:
    def __init__(self, key="ck_test"):
        self._c = KeyedClient("composio")
        if key:
            self._c.load(key)

    def client(self, provider):
        assert provider == "composio"
        return self._c


class Holder:
    def __init__(self, key="ck_test"):
        self.manager = Manager(key)


def composio(events, accounts=1, seen=None):
    def handle(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        assert request.headers["x-api-key"] == "ck_test"
        if request.url.path.endswith("/connected_accounts"):
            assert request.url.params["toolkit_slugs"] == "googlecalendar"
            return httpx.Response(200, json={"items": [{"id": "ca_123", "status": "ACTIVE",
                                                         "toolkit": {"slug": "googlecalendar"}}][:accounts]})
        assert request.url.path.endswith("/tools/execute/GOOGLECALENDAR_EVENTS_LIST")
        body = json.loads(request.content)
        assert body["connected_account_id"] == "ca_123"
        return httpx.Response(200, json={"data": {"items": events}, "successful": True, "error": None})
    return httpx.MockTransport(handle)


EVENTS = [
    {"summary": "CHEM 142 Lab", "location": "Thorvaldson 1B10\nSaskatoon", "status": "confirmed",
     "start": {"dateTime": "2026-11-20T13:30:00-06:00"}, "end": {"dateTime": "2026-11-20T16:20:00-06:00"}},
    {"summary": "GE 122 Lecture", "location": "ARTS 101",
     "start": {"dateTime": "2026-11-20T14:30:00Z"}, "end": {"dateTime": "2026-11-20T15:50:00Z"}},   # 8:30 his time
    {"summary": "Laundry", "start": {"date": "2026-11-20"}, "end": {"date": "2026-11-21"}},
    {"summary": "Cancelled thing", "status": "cancelled", "start": {"dateTime": "2026-11-20T09:00:00-06:00"}},
]


def test_days_are_read_the_way_he_says_them():
    assert which_day("today", THU) == THU
    assert which_day("Tomorrow", THU) == date(2026, 11, 20)
    assert which_day("friday", THU) == date(2026, 11, 20)
    assert which_day("thursday", THU) == THU                    # today counts
    assert which_day("next thursday", THU) == date(2026, 11, 26)
    assert which_day("2026-12-01", THU) == date(2026, 12, 1)
    with pytest.raises(CalendarError):
        which_day("the day after the exam", THU)


def test_events_come_back_in_order_in_his_time_with_rooms():
    events = parse_events(EVENTS, CST)
    assert [e.line() for e in events] == [
        "Fri 20 Nov · all day · Laundry",
        "Fri 20 Nov · 8:30 AM–9:50 AM · GE 122 Lecture · ARTS 101",
        "Fri 20 Nov · 1:30 PM–4:20 PM · CHEM 142 Lab · Thorvaldson 1B10",
    ]


def test_one_question_is_one_call_after_the_first_and_repeats_come_from_the_cache():
    seen = []
    cal = CalendarClient(Holder(), zone=CST, transport=composio(EVENTS, seen=seen))

    async def main():
        a = await cal.events(date(2026, 11, 20))
        b = await cal.events(date(2026, 11, 20))
        c = await cal.events(date(2026, 11, 21))
        return a, b, c

    a, b, c = asyncio.run(main())
    assert len(a) == 3 and b is a and c == []
    assert [r.url.path.rsplit("/", 1)[-1] for r in seen] == ["connected_accounts", "GOOGLECALENDAR_EVENTS_LIST",
                                                              "GOOGLECALENDAR_EVENTS_LIST"]
    args = json.loads(seen[1].content)["arguments"]
    assert args["timeMin"] == "2026-11-20T00:00:00-06:00" and args["timeMax"] == "2026-11-21T00:00:00-06:00"
    assert args["singleEvents"] is True and args["orderBy"] == "startTime" and args["calendarId"] == "primary"


def test_it_says_in_words_what_is_missing():
    async def events(cal):
        return await cal.events(THU)

    with pytest.raises(CalendarError, match="no Composio key"):
        asyncio.run(events(CalendarClient(Holder(key=None), zone=CST, transport=composio(EVENTS))))
    with pytest.raises(NotConnected, match="isn't connected in Composio"):
        asyncio.run(events(CalendarClient(Holder(), zone=CST, transport=composio(EVENTS, accounts=0))))

    def refuse(request):
        return httpx.Response(401, json={"error": {"message": "bad key"}})

    with pytest.raises(CalendarError, match="turned the key down"):
        asyncio.run(events(CalendarClient(Holder(), zone=CST, transport=httpx.MockTransport(refuse))))


def test_the_tool_answers_his_first_class_tomorrow(tmp_path):
    cal = CalendarClient(Holder(), zone=CST, transport=composio(EVENTS))
    cal.today = lambda: THU
    reg = default_registry()
    spec = reg.get("calendar")
    assert spec is not None and spec.voice == "loaded" and spec.tier == "read"
    ctx = ToolContext(root=tmp_path, calendar=cal)
    out = asyncio.run(reg.run("calendar", {"day": "tomorrow"}, ctx))
    assert not out.is_error
    lines = out.content.splitlines()
    assert "Friday 20 November" in lines[0] and "today is Thursday 19 November" in lines[0]
    assert lines[2] == "Fri 20 Nov · 8:30 AM–9:50 AM · GE 122 Lecture · ARTS 101"     # the first class
    off = asyncio.run(reg.run("calendar", {"day": "tomorrow"}, ToolContext(root=tmp_path)))
    assert off.is_error                                                               # no calendar service: off


def test_every_tool_is_loaded_for_a_spoken_turn_and_the_guide_sends_schedule_questions_to_the_calendar(tmp_path):
    from jarvis.tools.voice import ROUTING

    reg = default_registry()
    cal = CalendarClient(Holder(), zone=CST, transport=composio(EVENTS))

    class Anything:
        needs_sign_in = False

    ctx = ToolContext(root=tmp_path, calendar=cal, browser=Anything(), canvas=Anything(), memory=Anything(),
                      tasks=Anything(), documents=Anything(), questions=Anything())
    tools = reg.voice_tools(ctx)
    assert not any(t.get("defer_loading") for t in tools)                 # no search round trip before a tool
    assert not any(str(t.get("type", "")).startswith("tool_search") for t in tools)
    assert {"calendar", "canvas_find", "sign_in"} <= {t.get("name") for t in tools}
    assert "calendar" in ROUTING and "never answer a schedule question from Canvas" in ROUTING
    assert "speech-to-text" in ROUTING                                    # he knows the words may be misheard


# ---- v0.15.3: connecting Google Calendar is a card in his own browser, and Jarvis carries on by himself ----------
def project(state, seen=None):
    """A Composio project: no Google Calendar connection until state["connected"]; maybe no auth config yet."""
    def handle(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append((request.method, request.url.path.rsplit("/api/v3.1", 1)[1]))
        assert request.headers["x-api-key"] == "ck_test"
        path = request.url.path
        if path.endswith("/connected_accounts") and request.method == "GET":
            items = [{"id": "ca_new", "status": "ACTIVE"}] if state.get("connected") else []
            return httpx.Response(200, json={"items": items})
        if path.endswith("/auth_configs") and request.method == "GET":
            assert request.url.params["toolkit_slug"] == "googlecalendar"
            return httpx.Response(200, json={"items": [{"id": "ac_have", "status": "ENABLED"}] if state.get("config") else []})
        if path.endswith("/auth_configs") and request.method == "POST":
            body = json.loads(request.content)
            assert body == {"toolkit": {"slug": "googlecalendar"}, "auth_config": {"type": "use_composio_managed_auth"}}
            return httpx.Response(201, json={"toolkit": {"slug": "googlecalendar"}, "auth_config": {"id": "ac_made"}})
        if path.endswith("/connected_accounts/link"):
            body = json.loads(request.content)
            state["linked_with"] = body
            return httpx.Response(201, json={"redirect_url": "https://connect.composio.dev/link/lk_abc",
                                             "connected_account_id": "ca_new", "expires_at": "2026-11-20T03:00:00Z"})
        assert path.endswith("/tools/execute/GOOGLECALENDAR_EVENTS_LIST")
        return httpx.Response(200, json={"data": {"items": EVENTS}, "successful": True, "error": None})
    return httpx.MockTransport(handle)


def test_a_connect_link_uses_the_projects_set_up_or_makes_one():
    state, seen = {"config": True}, []
    cal = CalendarClient(Holder(), zone=CST, transport=project(state, seen))
    assert asyncio.run(cal.connect_link()) == "https://connect.composio.dev/link/lk_abc"
    assert state["linked_with"] == {"auth_config_id": "ac_have", "user_id": "jarvis"}
    assert ("POST", "/auth_configs") not in seen
    state = {}
    cal = CalendarClient(Holder(), zone=CST, transport=project(state))
    asyncio.run(cal.connect_link())
    assert state["linked_with"]["auth_config_id"] == "ac_made"        # none yet: Composio's own Google sign-in


def test_not_connected_puts_a_card_on_screen_and_carries_on_when_he_has_connected(tmp_path, monkeypatch):
    reg = default_registry()
    handler = reg.handlers["calendar"].__globals__
    monkeypatch.setitem(handler, "WATCH_EVERY_S", 0.01)
    state, told = {"config": True}, []

    async def resume(note):
        told.append(note)
        return True

    async def go():
        cal = CalendarClient(Holder(), zone=CST, transport=project(state))
        cal.today = lambda: THU
        ctx = ToolContext(root=tmp_path, calendar=cal, resume=resume)
        out = await reg.run("calendar", {"day": "tomorrow"}, ctx)
        await asyncio.sleep(0.05)
        assert told == []                                   # nothing yet: he hasn't allowed it
        state["connected"] = True                           # he clicked the card and allowed it in his browser
        for _ in range(100):
            if told:
                break
            await asyncio.sleep(0.01)
        after = await reg.run("calendar", {"day": "tomorrow"}, ctx)
        return out, after

    out, after = asyncio.run(go())
    assert not out.is_error and "isn't connected yet" in out.content and "one short line" in out.content
    kind, window = out.show
    page = window["data"]["pages"][0]
    assert kind == "window.push" and window["type"] == "web" and window["title"] == "Connect Google Calendar"
    assert page["url"] == "https://connect.composio.dev/link/lk_abc" and page["frame"] == "no"   # never inside the hub
    assert len(told) == 1 and "Google Calendar is connected now" in told[0] and "not something De Wet said" in told[0]
    assert "GE 122 Lecture" in after.content                # and now the answer is there


def test_no_key_is_said_in_words_and_no_page_is_opened(tmp_path):
    reg = default_registry()
    cal = CalendarClient(Holder(key=None), zone=CST, transport=project({}))
    out = asyncio.run(reg.run("calendar", {}, ToolContext(root=tmp_path, calendar=cal)))
    assert out.is_error and out.show is None
    text = out.content if isinstance(out.content, str) else json.dumps(out.content)
    assert "Controls › Keys" in text and "don't open any page" in text


def test_a_sign_in_page_is_never_put_inside_a_hub_window(tmp_path):
    reg = default_registry()
    out = asyncio.run(reg.run("show_page", {"pages": [
        {"url": "https://platform.composio.dev/", "title": "Composio"},
        {"url": "https://accounts.google.com/signin", "title": "Google sign-in"},
        {"url": "https://en.wikipedia.org/wiki/Saskatoon", "title": "Saskatoon"}]}, ToolContext(root=tmp_path)))
    pages = {p["title"]: p.get("frame") for p in out.show[1]["data"]["pages"]}
    assert pages == {"Composio": "no", "Google sign-in": "no", "Saskatoon": None}
    assert "opens in his own browser" in out.content and "Saskatoon can't" not in out.content


# -- v0.19.2: Laptop B, 2026-11-22: the account list answered 200, then every calendar call was refused with 400 ----

def test_the_calendars_own_account_is_used_even_when_composio_lists_other_apps_first():
    def handle(request):
        if request.url.path.endswith("/connected_accounts"):       # as if the toolkit filter were ignored
            return httpx.Response(200, json={"items": [
                {"id": "ca_gmail", "status": "ACTIVE", "toolkit": {"slug": "gmail"}, "user_id": "someone"},
                {"id": "ca_cal", "status": "ACTIVE", "toolkit": {"slug": "GOOGLECALENDAR"}, "user_id": "jarvis"}]})
        body = json.loads(request.content)
        if body["connected_account_id"] != "ca_cal":
            return httpx.Response(400, json={"error": {"message": "Connected account does not belong to toolkit googlecalendar"}})
        return httpx.Response(200, json={"data": {"items": EVENTS}, "successful": True})

    got = asyncio.run(CalendarClient(Holder(), zone=CST, transport=httpx.MockTransport(handle)).events(THU, 2))
    assert got and got[0].title

    def only_gmail(request):
        return httpx.Response(200, json={"items": [{"id": "ca_gmail", "status": "ACTIVE", "toolkit": {"slug": "gmail"}}]})

    with pytest.raises(NotConnected):
        asyncio.run(CalendarClient(Holder(), zone=CST, transport=httpx.MockTransport(only_gmail)).events(THU))


def test_a_refusal_says_composios_reason_tries_once_with_the_user_and_keeps_one_connection(caplog):
    made, bodies = [], []
    real = httpx.AsyncClient

    def handle(request):
        if request.url.path.endswith("/connected_accounts"):
            return httpx.Response(200, json={"items": [{"id": "ca_123", "status": "ACTIVE", "toolkit": {"slug": "googlecalendar"}, "user_id": "jarvis"}]})
        bodies.append(json.loads(request.content))
        if bodies[-1].get("user_id") != "jarvis":      # Composio on Laptop B: "User ID is required with connected account"
            return httpx.Response(400, json={"error": {"message": "User ID is required with connected account"}})
        return httpx.Response(200, json={"data": {"items": EVENTS}, "successful": True})

    class Counting(real):
        def __init__(self, *a, **k):
            made.append(1)
            super().__init__(*a, **k)

    async def twice():
        cal = CalendarClient(Holder(), zone=CST, transport=httpx.MockTransport(handle))
        first = await cal.events(THU, 2)
        await cal.events(THU, 3)
        return first

    httpx.AsyncClient = Counting
    try:
        with caplog.at_level("WARNING", logger="jarvis.reach"):
            assert asyncio.run(twice())
    finally:
        httpx.AsyncClient = real
    assert len(made) == 1                                           # one HTTPS client, not one per call (2.4 to 4.8 s each on Laptop B)
    assert [b.get("user_id") for b in bodies] == ["jarvis", "jarvis"]   # named from the first call: no refused first try
    assert not [r for r in caplog.records if r.getMessage() == "calendar.refused"]

    def always(request):
        if request.url.path.endswith("/connected_accounts"):
            return httpx.Response(200, json={"items": [{"id": "ca_123", "status": "ACTIVE", "toolkit": {"slug": "googlecalendar"}}]})
        return httpx.Response(400, json={"message": "timeMin must be RFC3339"})

    with caplog.at_level("WARNING", logger="jarvis.reach"), pytest.raises(CalendarError, match=r"error \(400: timeMin must be RFC3339\)"):
        asyncio.run(CalendarClient(Holder(), zone=CST, transport=httpx.MockTransport(always)).events(THU))
    refused = [r for r in caplog.records if r.getMessage() == "calendar.refused"]
    assert refused and refused[0].status == 400 and refused[0].reason == "timeMin must be RFC3339"


def test_canvas_needing_sign_in_tells_jarvis_what_to_do(tmp_path):
    from types import SimpleNamespace

    from jarvis.canvas import SignInNeeded
    from jarvis.tools.base import ToolError
    from jarvis.tools.canvas_find import handler as find
    from jarvis.tools.canvas_read import handler as read

    class Canvas:
        async def find(self, *a, **k): raise SignInNeeded("sign in")
        async def read(self, *a, **k): raise SignInNeeded("sign in")

    ctx = SimpleNamespace(canvas=Canvas(), documents=None)
    for call in (find.run({"query": "due this week"}, ctx), read.run({"link": "/courses/1"}, ctx)):
        with pytest.raises(ToolError, match="Call sign_in with site canvas"):
            asyncio.run(call)
