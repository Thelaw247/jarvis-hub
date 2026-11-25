"""Two laptops, one change (v0.24.0): a laptop that runs its own Jarvis can send a new key or voice ID to the other
laptop's Jarvis too. The key is never read, kept or logged on the way; it only crosses over https or to this laptop."""
import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from jarvis_hub import keys_proxy, live

HERE, THERE = ("http://127.0.0.1:8770", "token-here"), ("https://laptop-b.tail1234.ts.net", "token-there")
BODY = b'{"secret":"not-a-real-key"}'
JSON = {"Content-Type": "application/json"}
ALSO = {**JSON, keys_proxy.ALSO_HEADER: "1"}


def pretend(seen, answer=None, status=200):
    def core(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, str(request.url), request.headers.get("x-jarvis-session"), request.content))
        return httpx.Response(status, json=answer if answer is not None else {"id": "elevenlabs", "status": "next_waiting"})
    return httpx.MockTransport(core)


def hub(here, there, other=THERE):
    app = FastAPI()
    app.include_router(keys_proxy.build_router(*HERE, transport=here, other=other, other_transport=there))
    app.include_router(live.build_router(HERE, transport=here, other=other, other_transport=there))
    return TestClient(app)


def test_the_other_laptop_is_only_known_to_a_laptop_running_its_own_jarvis(monkeypatch):
    for name in ("JARVIS_REMOTE_CORE_URL", "JARVIS_REMOTE_CORE_SESSION"):
        monkeypatch.delenv(name, raising=False)
    assert keys_proxy.other_target(HERE) is None  # nothing saved
    monkeypatch.setenv("JARVIS_REMOTE_CORE_URL", THERE[0] + "/")
    monkeypatch.setenv("JARVIS_REMOTE_CORE_SESSION", THERE[1])
    assert keys_proxy.other_target(HERE) == THERE
    assert keys_proxy.other_target(THERE) is None  # this hub is using the other laptop's Jarvis: there is only one
    assert keys_proxy.other_target(("https://laptop-c.tail1234.ts.net", "x")) is None
    monkeypatch.setenv("JARVIS_REMOTE_CORE_URL", "http://laptop-b.tail1234.ts.net")
    assert keys_proxy.other_target(HERE) is None  # a key never crosses in the clear
    assert keys_proxy.laptop_name(HERE[0]) == "here" and keys_proxy.laptop_name(THERE[0]) == "laptop-b"


def test_a_new_key_goes_to_both_only_when_he_ticks_it():
    here, there = [], []
    c = hub(pretend(here), pretend(there))
    listing = c.get("/api/keys")
    assert listing.headers["x-jarvis-kept"] == "here" and listing.headers["x-jarvis-other-name"] == "laptop-b"
    assert there == []  # looking never touches the other laptop
    plain = c.post("/api/keys/elevenlabs/next", content=BODY, headers=JSON)
    assert "x-jarvis-other" not in plain.headers and there == []  # not ticked: this laptop only
    both = c.post("/api/keys/elevenlabs/next", content=BODY, headers=ALSO)
    assert both.headers["x-jarvis-other"] == "saved" and both.json()["status"] == "next_waiting"  # this laptop's answer, as it came
    assert there == [("POST", THERE[0] + "/api/keys/elevenlabs/next", "token-there", BODY)]
    assert c.post("/api/keys/elevenlabs/promote", headers=ALSO).headers["x-jarvis-other"] == "saved"
    assert c.delete("/api/keys/elevenlabs/previous", headers=ALSO).headers["x-jarvis-other"] == "saved"
    assert [s[1].rsplit("/", 1)[-1] for s in there] == ["next", "promote", "previous"]
    gone = c.request("DELETE", "/api/keys/elevenlabs", content=b'{"confirm":"elevenlabs"}', headers=ALSO)
    assert gone.status_code == 200 and "x-jarvis-other" not in gone.headers and len(there) == 3  # removing stays on one laptop


def test_a_key_this_laptop_refused_is_not_sent_on():
    there = []
    failed = {"id": "elevenlabs", "status": "failed_check", "next": {"check": "failed"}}
    assert "x-jarvis-other" not in hub(pretend([], failed), pretend(there)).post("/api/keys/elevenlabs/next", content=BODY, headers=ALSO).headers
    assert "x-jarvis-other" not in hub(pretend([], {"error": "view_only"}, 403), pretend(there)).post("/api/keys/elevenlabs/next", content=BODY, headers=ALSO).headers
    assert there == []
    cross = hub(pretend([]), pretend(there)).post("/api/keys/elevenlabs/next", content=BODY, headers={**ALSO, "Origin": "https://evil.example"})
    assert cross.status_code == 403 and there == []  # another site's page reaches neither laptop


def test_it_says_when_the_other_laptop_did_not_take_it():
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("asleep")

    c = hub(pretend([]), httpx.MockTransport(down))
    answer = c.post("/api/keys/elevenlabs/next", content=BODY, headers=ALSO)
    assert answer.status_code == 200 and answer.headers["x-jarvis-other"] == "unreachable"  # this laptop still took it
    assert hub(pretend([]), pretend([], {"error": "no_next"}, 409)).post("/api/keys/elevenlabs/promote", headers=ALSO).headers["x-jarvis-other"] == "refused"
    failed = {"id": "elevenlabs", "next": {"check": "failed"}}
    assert hub(pretend([]), pretend([], failed)).post("/api/keys/elevenlabs/next", content=BODY, headers=ALSO).headers["x-jarvis-other"] == "refused"


def test_the_voice_id_goes_to_both_the_same_way():
    here, there = [], []
    c = hub(pretend(here, {"voice_id": "JBFqnCBsd6RMkjVDRZzb"}), pretend(there, {"voice_id": "JBFqnCBsd6RMkjVDRZzb"}))
    assert c.get("/api/settings").headers["x-jarvis-other-name"] == "laptop-b" and there == []
    voice = b'{"voice_id":"JBFqnCBsd6RMkjVDRZzb"}'
    assert "x-jarvis-other" not in c.put("/api/settings/voice", content=voice, headers=JSON).headers and there == []
    assert c.put("/api/settings/voice", content=voice, headers=ALSO).headers["x-jarvis-other"] == "saved"
    assert there == [("PUT", THERE[0] + "/api/settings/voice", "token-there", voice)]


def test_one_jarvis_means_no_second_copy_and_no_tick_box():
    there = []
    c = hub(pretend([]), pretend(there), other=None)
    listing = c.get("/api/keys")
    assert listing.headers["x-jarvis-kept"] == "here" and "x-jarvis-other-name" not in listing.headers
    assert "x-jarvis-other" not in c.post("/api/keys/elevenlabs/next", content=BODY, headers=ALSO).headers and there == []
    app = FastAPI()  # Laptop A using Laptop B's Jarvis: the page says where the one copy is
    app.include_router(keys_proxy.build_router(*THERE, transport=pretend([])))
    assert TestClient(app).get("/api/keys").headers["x-jarvis-kept"] == "laptop-b"
