"""K1: API keys, core side. Fake keyring, fake providers (or httpx MockTransport): no network, no real keys."""
from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from referencing import Registry as SchemaRegistry
from referencing import Resource

from jarvis.secrets import (
    AuthFailed,
    CheckResult,
    KeyManager,
    KeysError,
    MemoryBackend,
    MetaFile,
    Provider,
    Registry,
    Session,
    build_router,
    default_providers,
    default_registry,
    ip_allowed,
    service_name,
)

# Made-up test keys (never real). Each has a distinctive body so a leak of any part is easy to grep for.
OLD = "sk-ant-api03-TESTONLYoldKEYbody0000000000000000-OLD1"
NEW = "sk-ant-api03-TESTONLYnewKEYbody1111111111111111-NEW2"
BAD = "sk-ant-api03-TESTONLYbadKEYbody2222222222222222-BAD3"
VOICE = "TESTONLYvoiceKEYbody3333333333333333-VOX4"
PASSWORD = "TESTONLY restic pass phrase 4444"
ALL_SECRETS = [OLD, NEW, BAD, VOICE, PASSWORD]


def bodies(secrets=ALL_SECRETS) -> list[str]:
    """What must never appear anywhere: every key minus its last 4 characters (the last 4 may be shown)."""
    return [s[:-4] for s in secrets] + [s[4:-4] for s in secrets]


class Clock:
    def __init__(self, t: float = 1_800_000_000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


@dataclass
class FakeProvider(Provider):
    """Checks against a set of keys the fake provider accepts."""

    good: set = field(default_factory=set)
    checks: int = 0

    async def _check(self, secret, aux):
        self.checks += 1
        await asyncio.sleep(0)
        return CheckResult(secret in self.good, None if secret in self.good else "rejected")


class Harness:
    def __init__(self, tmp_path: Path) -> None:
        self.clock = Clock()
        self.backend = MemoryBackend()
        self.events: list[tuple[str, dict]] = []
        self.anthropic = FakeProvider("anthropic", "Claude (Anthropic API)", "Claude key", good={OLD, NEW})
        self.voice = FakeProvider("elevenlabs", "ElevenLabs (voice)", "ElevenLabs key", good={VOICE})
        real = {p.id: p for p in default_providers()}
        self.registry = Registry([self.anthropic, self.voice, real["composio"], real["restic"], real["google-oauth"],
                                  real["openweather"]])
        self.meta_path = tmp_path / "state" / "keys.json"
        self.mgr = self.make()

    def make(self) -> KeyManager:
        return KeyManager(self.backend, self.registry, MetaFile(self.meta_path), clock=self.clock,
                          emit=lambda kind, data: self.events.append((kind, data)))

    def stored(self, slot: str, pid: str = "anthropic") -> str | None:
        return self.backend.items.get(service_name(pid, slot))

    async def live(self, secret: str = OLD) -> None:
        await self.mgr.add_next("anthropic", secret)
        await self.mgr.promote("anthropic")


@pytest.fixture
def h(tmp_path):
    return Harness(tmp_path)


def run(coro):
    return asyncio.run(coro)


# ---- contract ----------------------------------------------------------------------------------------------------
CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
SCHEMAS = {p.name: json.loads(p.read_text(encoding="utf-8")) for p in CONTRACTS.glob("*.schema.json")}
SCHEMA_REG = SchemaRegistry().with_resources((n, Resource.from_contents(d)) for n, d in SCHEMAS.items())


def problems(doc, part: str | None = None) -> list[str]:
    ref = "keys.schema.json" + (f"#/$defs/{part}" if part else "")
    return [f"{list(e.path)}: {e.message}" for e in Draft202012Validator({"$ref": ref}, registry=SCHEMA_REG).iter_errors(doc)]


def test_listing_and_events_match_the_contract(h):
    async def go():
        assert problems(h.mgr.listing()) == []
        await h.live()
        await h.mgr.add_next("anthropic", NEW)
        await h.mgr.add_next("elevenlabs", "nope")  # bad shape
        await h.mgr.add_next("restic", PASSWORD)
        await h.mgr.promote("restic")
    run(go())
    listing = h.mgr.listing()
    assert problems(listing) == []
    for kind, data in h.events:
        if kind == "keys.updated":
            assert problems(data, "updated") == []
        else:
            assert kind == "activity.added" and data["category"] == "keys" and {"id", "ts", "what", "why"} <= set(data)
    assert {e["what"] for e in listing["audit"]} >= {"made_live", "added", "failed_check"}


def test_default_rows_are_the_four_services_and_google_is_optional(tmp_path):
    reg = default_registry()
    mgr = KeyManager(MemoryBackend(), reg, MetaFile(tmp_path / "k.json"))
    listing = mgr.listing()
    assert [r["id"] for r in listing["rows"]] == ["anthropic", "elevenlabs", "composio", "restic"]
    assert all(r["status"] == "missing" for r in listing["rows"])
    assert [a["id"] for a in listing["addable"]] == ["google-oauth", "openweather"]
    assert problems(listing) == []


# ---- rotation ----------------------------------------------------------------------------------------------------
def test_full_rotation_with_requests_in_flight_has_zero_failures(h):
    valid = {OLD, NEW}  # the provider accepts both until he revokes the old one
    swapped = asyncio.Event()
    seen: list[tuple[bool, str]] = []

    async def request(key):
        started_after_swap = swapped.is_set()
        await asyncio.sleep(random.uniform(0, 0.004))
        if key not in valid:
            raise AuthFailed(401)
        seen.append((started_after_swap, key))
        return key

    async def go():
        await h.live(OLD)
        row = await h.mgr.add_next("anthropic", NEW)
        assert row["status"] == "next_waiting" and row["live"]["last4"] == OLD[-4:]
        client = h.mgr.client("anthropic")
        tasks = []
        for i in range(400):
            tasks.append(asyncio.create_task(client.call(request)))
            if i == 200:
                await h.mgr.promote("anthropic")
                swapped.set()
            await asyncio.sleep(0)
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results

    results = run(go())
    failures = [r for r in results if isinstance(r, BaseException)]
    assert failures == []
    assert {k for _, k in seen} == {OLD, NEW}  # some finished on the old key, the rest used the new one
    assert all(k == NEW for after, k in seen if after)
    assert h.stored("live") == NEW and h.stored("previous") == OLD and h.stored("next") is None
    row = h.mgr.row("anthropic")
    assert row["status"] == "live" and row["previous"]["last4"] == OLD[-4:] and "until" in row["previous"]
    assert any(d.get("audit", {}).get("text") == "Claude key replaced" for k, d in h.events if k == "keys.updated")


def test_a_failed_check_is_never_promoted(h):
    async def go():
        await h.live(OLD)
        row = await h.mgr.add_next("anthropic", BAD)
        assert row["status"] == "failed_check" and row["next"]["reason"] == "rejected"
        assert h.stored("next") is None  # a refused key isn't kept
        with pytest.raises(KeysError) as err:
            await h.mgr.promote("anthropic")
        assert err.value.status == 409
        assert h.stored("live") == OLD and h.mgr.client("anthropic").lease().secret == OLD

        bad_shape = await h.mgr.add_next("anthropic", "not a key")
        assert bad_shape["next"]["reason"] == "bad_shape" and bad_shape["next"]["last4"] is None
        with pytest.raises(KeysError):
            await h.mgr.promote("anthropic")

        # passed its check, but the key was revoked before he pressed "make live": the re-check stops it
        await h.mgr.add_next("anthropic", NEW)
        h.anthropic.good.discard(NEW)
        h.clock.t += 11 * 60
        with pytest.raises(KeysError) as err:
            await h.mgr.promote("anthropic")
        assert err.value.code == "next_not_checked" and err.value.row["status"] == "failed_check"
        assert h.stored("live") == OLD and h.mgr.client("anthropic").lease().secret == OLD
    run(go())


def test_falls_back_to_the_previous_key_on_401_within_the_window(h):
    valid = {OLD}  # the new key passed its check but the provider refuses it once live

    async def request(key):
        await asyncio.sleep(0.001)
        if key not in valid:
            raise httpx.HTTPStatusError("x", request=httpx.Request("GET", "https://example.invalid"),
                                        response=httpx.Response(401))
        return key

    async def go():
        await h.live(OLD)
        await h.mgr.add_next("anthropic", NEW)
        await h.mgr.promote("anthropic")
        h.clock.t += 5 * 60
        client = h.mgr.client("anthropic")
        return await asyncio.gather(*(client.call(request) for _ in range(25)))

    results = run(go())
    assert results == [OLD] * 25  # every request succeeded (retried once on the previous key)
    row = h.mgr.row("anthropic")
    assert row["status"] == "fell_back" and row["next"]["reason"] == "refused_after_swap"
    assert row["live"]["last4"] == OLD[-4:] and row["previous"] is None
    assert h.stored("live") == OLD and h.stored("previous") is None and h.stored("next") is None
    fell = [d for k, d in h.events if k == "keys.updated" and d.get("audit", {}).get("what") == "fell_back"]
    assert len(fell) == 1 and fell[0]["row"]["status"] == "fell_back"
    # the flag stays until he acts, and survives a restart
    restarted = h.make()
    restarted.load()
    assert restarted.row("anthropic")["status"] == "fell_back"
    assert restarted.client("anthropic").lease().secret == OLD


def test_no_fall_back_after_the_window(h):
    async def request(key):
        if key == NEW:
            raise AuthFailed(403)
        return key

    async def go():
        await h.live(OLD)
        await h.mgr.add_next("anthropic", NEW)
        await h.mgr.promote("anthropic")
        h.clock.t += 15 * 60 + 1
        with pytest.raises(AuthFailed):
            await h.mgr.client("anthropic").call(request)
    run(go())
    assert h.mgr.row("anthropic")["status"] == "live"


def test_previous_is_removed_after_the_window(h):
    async def go():
        await h.live(OLD)
        await h.mgr.add_next("anthropic", NEW)
        await h.mgr.promote("anthropic")
        h.clock.t += 14 * 60
        assert await h.mgr.sweep() == []
        assert h.stored("previous") == OLD
        h.clock.t += 60
        assert await h.mgr.sweep() == ["anthropic"]
    run(go())
    assert h.stored("previous") is None and not h.mgr.client("anthropic").has_previous
    row = h.mgr.row("anthropic")
    assert row["previous"] is None and row["live"]["last4"] == NEW[-4:]
    assert h.mgr.listing()["audit"][0]["what"] == "previous_removed"
    acts = [d for k, d in h.events if k == "activity.added"]
    assert "revoke" in acts[-1]["why"]


def test_the_watchdog_loop_sweeps_on_its_own(h):
    ticks = []

    async def fake_sleep(s):
        ticks.append(s)
        h.clock.t += 5 * 60
        if len(ticks) >= 4:
            raise asyncio.CancelledError

    async def go():
        await h.live(OLD)
        await h.mgr.add_next("anthropic", NEW)
        await h.mgr.promote("anthropic")
        with pytest.raises(asyncio.CancelledError):
            await h.mgr.watchdog(interval_s=30, sleep=fake_sleep)
    run(go())
    assert h.stored("previous") is None and ticks == [30] * 4


def test_remove_needs_confirm_and_clears_every_slot(h):
    async def go():
        await h.live(OLD)
        await h.mgr.add_next("anthropic", NEW)
        await h.mgr.promote("anthropic")
        with pytest.raises(KeysError) as err:
            await h.mgr.remove("anthropic", True)
        assert err.value.code == "confirm_required" and h.stored("live") == NEW
        row = await h.mgr.remove("anthropic", "anthropic")
        assert row["status"] == "missing"
    run(go())
    assert not [k for k in h.backend.items if k.startswith("Jarvis/anthropic/")]


def test_keys_survive_a_restart_and_unknown_services_are_refused(h):
    run(h.live(OLD))
    again = h.make()
    again.load()
    assert again.client("anthropic").lease().secret == OLD
    with pytest.raises(KeysError) as err:
        again.row("nope")
    assert err.value.status == 404


def test_credential_manager_down_is_a_503_without_detail(h):
    h.backend.fail = True
    with pytest.raises(KeysError) as err:
        run(h.mgr.add_next("anthropic", OLD))
    assert err.value.status == 503 and err.value.code == "store_unavailable"


# ---- secrets never leak ------------------------------------------------------------------------------------------
SESSION = "hub-session-token-for-tests"


def verifier(token):
    return {SESSION: Session(), "phone": Session(can_write=False)}.get(token)


def app_for(h) -> FastAPI:
    app = FastAPI()
    app.include_router(build_router(h.mgr, verifier))
    return app


def test_secrets_never_appear_in_responses_logs_events_or_the_metadata_file(h, caplog):
    caplog.set_level(logging.DEBUG)
    http = TestClient(app_for(h), client=("127.0.0.1", 5000))
    hdr = {"X-Jarvis-Session": SESSION}
    texts = []

    def call(method, path, body=None):
        r = http.request(method, path, headers=hdr, json=body)
        texts.append(r.text)
        return r

    assert call("POST", "/api/keys/anthropic/next", {"secret": OLD}).json()["status"] == "next_waiting"
    assert call("POST", "/api/keys/anthropic/promote").json()["status"] == "live"
    assert call("POST", "/api/keys/anthropic/next", {"secret": BAD}).json()["status"] == "failed_check"
    assert call("POST", "/api/keys/anthropic/next", {"secret": NEW}).json()["status"] == "next_waiting"
    assert call("POST", "/api/keys/anthropic/promote").json()["previous"]["last4"] == OLD[-4:]
    assert call("POST", "/api/keys/elevenlabs/next", {"secret": VOICE}).status_code == 200
    assert call("POST", "/api/keys/restic/next", {"secret": PASSWORD}).json()["next"]["last4"] is None
    assert call("POST", "/api/keys/restic/promote").json()["status"] == "live"
    assert call("DELETE", "/api/keys/anthropic/previous").json()["previous"] is None
    # malformed bodies must not be echoed back (FastAPI's own 422s would echo them)
    assert call("POST", "/api/keys/elevenlabs/next", {"secret": VOICE, "extra": OLD}).status_code == 400
    assert call("POST", "/api/keys/elevenlabs/next", {"secret": NEW * 500}).status_code == 400
    assert call("POST", "/api/keys/elevenlabs/next", {"key": BAD}).status_code == 400
    r = call("GET", "/api/keys")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    assert call("DELETE", "/api/keys/elevenlabs", {"confirm": "elevenlabs"}).json()["status"] == "missing"

    haystacks = {
        "responses": "\n".join(texts),
        "events": json.dumps(h.events),
        "logs": caplog.text + json.dumps([r.__dict__ for r in caplog.records], default=str),
        "metadata": h.meta_path.read_text(encoding="utf-8"),
    }
    for name, text in haystacks.items():
        for body in bodies():
            assert body not in text, f"key material in {name}"
    assert PASSWORD[-4:] not in haystacks["responses"]  # nothing of the password, not even its end
    assert h.stored("live", "restic") == PASSWORD  # …but it is in the (fake) Credential Manager


def test_real_provider_checks_do_not_leak_through_httpx_logs(caplog):
    caplog.set_level(logging.DEBUG)
    key = "TESTONLYweatherKEYbody5555555555555555-WTH5"
    transport = httpx.MockTransport(lambda req: httpx.Response(401, json={"message": f"Invalid API key {key}"}))
    client = httpx.AsyncClient(transport=transport)
    reg = default_registry(lambda: client)
    result = run(reg.get("openweather").check(key))
    assert result == CheckResult(False, "rejected")
    assert key[:-4] not in caplog.text and key[:-4] not in json.dumps([r.args for r in caplog.records], default=str)


# ---- provider checks (MockTransport: the real request code, no network) ------------------------------------------
def provider_with(pid, handler):
    seen = []

    def wrap(req):
        seen.append(req)
        return handler(req)

    client = httpx.AsyncClient(transport=httpx.MockTransport(wrap))
    return default_registry(lambda: client).get(pid), seen


def test_anthropic_check_is_a_models_call():
    p, seen = provider_with("anthropic", lambda req: httpx.Response(200, json={"data": []}))
    assert run(p.check(OLD)) == CheckResult(True)
    req = seen[0]
    assert req.url.host == "api.anthropic.com" and req.url.path == "/v1/models"
    assert req.headers["x-api-key"] == OLD and req.headers["anthropic-version"]
    assert run(p.check("not-an-anthropic-key")).reason == "bad_shape" and len(seen) == 1


@pytest.mark.parametrize("pid,host,path,header", [
    ("elevenlabs", "api.elevenlabs.io", "/v1/user/subscription", "xi-api-key"),
    ("composio", "backend.composio.dev", "/api/v3.1/connected_accounts", "x-api-key"),
])
def test_token_checks_call_the_right_endpoint(pid, host, path, header):
    p, seen = provider_with(pid, lambda req: httpx.Response(200, json={}))
    assert run(p.check(VOICE)).ok
    assert (seen[0].url.host, seen[0].url.path, seen[0].headers[header]) == (host, path, VOICE)


@pytest.mark.parametrize("code,reason", [(401, "rejected"), (403, "forbidden"), (429, "rate_limited"),
                                         (500, "provider_error")])
def test_check_failures_are_fixed_codes(code, reason):
    p, _ = provider_with("composio", lambda req: httpx.Response(code, text=f"bad key {VOICE}"))
    assert run(p.check(VOICE)) == CheckResult(False, reason)


def test_unreachable_provider():
    def boom(req):
        raise httpx.ConnectError("no route")
    p, _ = provider_with("elevenlabs", boom)
    assert run(p.check(VOICE)) == CheckResult(False, "unreachable")


GOOGLE = json.dumps({"installed": {"client_id": "123-test.apps.googleusercontent.com",
                                   "client_secret": "GOCSPX-TESTONLYgoogleSECRET-GG66",
                                   "token_uri": "https://evil.example/token", "redirect_uris": ["http://localhost"]}},
                    indent=2)


def test_google_client_shape_and_refresh():
    p, seen = provider_with("google-oauth", lambda req: httpx.Response(200, json={"access_token": "x",
                                                                                  "refresh_token_expires_in": 3600}))
    assert run(p.check(GOOGLE)) == CheckResult(True, shape_only=True)  # no refresh token yet: shape only
    assert seen == []
    result = run(p.check(GOOGLE, {"refresh_token": "1//TESTONLYrefresh"}))
    assert result.ok and result.expires and seen[0].url == "https://oauth2.googleapis.com/token"  # never the file's URL
    assert p.last4(p.validate(GOOGLE)) == "GG66"
    assert run(p.check('{"installed": {"client_id": "x"}}')).reason == "bad_shape"
    p400, _ = provider_with("google-oauth", lambda req: httpx.Response(400, json={"error": "invalid_grant"}))
    assert run(p400.check(GOOGLE, {"refresh_token": "1//TESTONLYrefresh"})).reason == "refresh_failed"


def test_google_expiring_status(tmp_path):
    clock = Clock()
    client = httpx.AsyncClient(transport=httpx.MockTransport(
        lambda req: httpx.Response(200, json={"refresh_token_expires_in": 2 * 24 * 3600})))
    reg = default_registry(lambda: client)
    mgr = KeyManager(MemoryBackend(), reg, MetaFile(tmp_path / "k.json"), clock=time.time)
    mgr.set_aux("google-oauth", "refresh_token", "1//TESTONLYrefresh")

    async def go():
        await mgr.add_next("google-oauth", GOOGLE)
        return await mgr.promote("google-oauth")
    row = run(go())
    assert row["status"] == "expiring" and row["live"]["expires"]
    listing = mgr.listing()
    assert "google-oauth" in [r["id"] for r in listing["rows"]] and problems(listing) == []
    assert clock  # (the real clock is used here: expiry comes from the provider's answer)


def test_restic_has_no_remote_check():
    p = default_registry().get("restic")
    assert run(p.check(PASSWORD)) == CheckResult(True, shape_only=True)
    assert p.last4(PASSWORD) is None
    assert run(p.check("short")).reason == "bad_shape"


# ---- the IP and token guard --------------------------------------------------------------------------------------
@pytest.mark.parametrize("host,ok", [
    ("127.0.0.1", True), ("::1", True), ("::ffff:127.0.0.1", True), ("100.64.0.1", True), ("100.127.255.254", True),
    ("fd7a:115c:a1e0::1234", True), ("100.128.0.1", False), ("192.168.1.20", False), ("10.0.0.5", False),
    ("8.8.8.8", False), ("testclient", False), ("", False), (None, False),
])
def test_ip_allowed(host, ok):
    assert ip_allowed(host) is ok


def test_the_api_needs_loopback_or_tailnet_and_a_session(h):
    app = app_for(h)
    body = {"secret": OLD}
    outside = TestClient(app, client=("192.168.1.20", 5000))
    r = outside.post("/api/keys/anthropic/next", json=body, headers={"X-Jarvis-Session": SESSION})
    assert r.status_code == 403 and r.json()["error"] == "not_allowed"
    tail = TestClient(app, client=("100.101.2.3", 5000))
    assert tail.get("/api/keys").status_code == 403  # no token
    assert tail.get("/api/keys", headers={"X-Jarvis-Session": "wrong"}).status_code == 403
    assert tail.get("/api/keys", headers={"X-Jarvis-Session": SESSION}).json()["can_write"] is True
    phone = {"X-Jarvis-Session": "phone"}
    listing = tail.get("/api/keys", headers=phone).json()
    assert listing["can_write"] is False and problems(listing) == []
    r = tail.post("/api/keys/anthropic/next", json=body, headers=phone)
    assert r.status_code == 403 and r.json()["error"] == "view_only"
    assert h.stored("next") is None  # nothing was stored by any refused request
    # forwarded-for headers are not trusted
    r = outside.get("/api/keys", headers={"X-Jarvis-Session": SESSION, "X-Forwarded-For": "127.0.0.1"})
    assert r.status_code == 403
    ok = tail.post("/api/keys/anthropic/next", json=body, headers={"X-Jarvis-Session": SESSION})
    assert ok.status_code == 200 and problems(ok.json(), "row") == []
    assert tail.post("/api/keys/zzz/next", json=body, headers={"X-Jarvis-Session": SESSION}).status_code == 404
    r = tail.delete("/api/keys/anthropic/previous", headers={"X-Jarvis-Session": SESSION})
    assert r.status_code == 409 and problems(r.json(), "error") == []


def test_async_verifier_and_broken_verifier(h):
    async def averify(token):
        return token == SESSION

    def broken(token):
        raise RuntimeError("boom")

    for v, code in ((averify, 200), (broken, 403)):
        app = FastAPI()
        app.include_router(build_router(h.mgr, v))
        r = TestClient(app, client=("127.0.0.1", 1)).get("/api/keys", headers={"X-Jarvis-Session": SESSION})
        assert r.status_code == code


# ---- latency: the swap and the per-request lease are T0 -----------------------------------------------------------
def test_swap_and_lease_are_well_under_a_millisecond(h):
    run(h.live(OLD))
    client = h.mgr.client("anthropic")
    n = 20000
    t0 = time.perf_counter()
    for i in range(n):
        client.swap(NEW if i % 2 else OLD)
        client.lease()
    per_op_ms = (time.perf_counter() - t0) * 1000 / n
    assert per_op_ms < 0.05, per_op_ms  # target: a swap costs < 1 ms (§3)
