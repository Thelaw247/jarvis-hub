"""K2: Controls › Keys. The secret never lands in the DOM, the store or web storage; keyboard order and labels;
view-only on the phone; the not-connected page (the hub's demo backend) accepts nothing.

A connected jarvis-core is played by Playwright routes answering /api/keys in the contract's shape
(contracts/keys.schema.json), so the real send path (keys-api.js) is what's tested."""
import json
import re

SECRET = "sk-ant-api03-K2TEST-q9W8e7R6t5Y4u3I2o1P0-zz9Z"
LAST4 = SECRET[-4:]
PIECE = SECRET[:16]  # any long piece of it counts as a leak too

# Every attribute, text node and form value in the document (and the store and web storage), as one string.
EVERYTHING = """() => {
  const out = [];
  for (const el of document.querySelectorAll('*')) {
    for (const a of el.attributes) out.push(a.value);
    if ('value' in el && typeof el.value === 'string') out.push(el.value);
  }
  out.push(document.documentElement.outerHTML, document.body.innerText);
  out.push(JSON.stringify(window.__jarvis.store.state));
  for (const s of [localStorage, sessionStorage]) for (let i = 0; i < s.length; i++) out.push(s.key(i), s.getItem(s.key(i)));
  return out.join('\\n');
}"""
WATCH_STORAGE = """() => { window.__writes = [];
  for (const name of ['setItem', 'removeItem', 'clear']) {
    const was = Storage.prototype[name];
    Storage.prototype[name] = function (...a) { window.__writes.push([this === localStorage ? 'local' : 'session', name, ...a]); return was.apply(this, a); };
  } }"""


def slot(last4, check="ok", **more):
    return {"last4": last4, "added": "2026-11-16T09:00:00", "checked": "2026-11-16T09:00:01", "check": check, **more}


def row(sid, label, status="live", **more):
    base = {"id": sid, "label": label, "kind": "token", "checkable": True, "console_url": f"https://console.example/{sid}",
            "status": status, "live": slot("AAAA"), "next": None, "previous": None, "used": "2026-11-16T15:39:50"}
    return {**base, **more}


def core_doc(can_write=True):
    return {"v": 2, "can_write": can_write, "rows": [
        row("anthropic", "Claude (Anthropic API)"), row("elevenlabs", "ElevenLabs (voice)"),
        row("composio", "Composio (Gmail, Calendar, Drive)"),
        row("restic", "Backup password (restic)", kind="password", checkable=False, live=slot(None, "shape_only"))],
        "addable": [{"id": "google-oauth", "label": "Google OAuth client", "kind": "client_json", "checkable": True}], "audit": []}


def fake_core(page, can_write=True):
    """Answer /api/keys like jarvis-core. Records every write (method, path, body) in the returned list."""
    sent, doc = [], core_doc(can_write)

    def handle(route):
        req = route.request
        if req.method == "GET":
            return route.fulfill(status=200, content_type="application/json", body=json.dumps(doc))
        sent.append((req.method, re.sub(r"^https?://[^/]+", "", req.url), req.post_data))
        r = next(x for x in doc["rows"] if req.url.split("/api/keys/")[1].startswith(x["id"]))
        if req.url.endswith("/next"):
            r.update(status="checking", next=slot(LAST4, "checking", checked=None))
        elif req.url.endswith("/promote"):
            r.update(status="live", previous={**r["live"], "until": "2026-11-16T15:55:00"}, live={**r["next"], "check": "ok"}, next=None)
        elif req.url.endswith("/previous"):
            r.update(previous=None)
        return route.fulfill(status=200, content_type="application/json", body=json.dumps(r))

    page.route(re.compile(r".*/api/keys(/.*)?(\?.*)?$"), handle)
    return sent, doc


def open_keys(hub, can_write=True, size=None):
    page = hub.page
    sent, doc = fake_core(page, can_write)
    hub.open("#/controls/keys", **({"size": size} if size else {}))
    page.wait_for_selector(".jv-keys__list")
    return page, sent, doc


# ---- the secret ---------------------------------------------------------------------------------------
def test_secret_is_sent_once_then_gone_from_dom_store_and_storage(hub):
    page, sent, doc = open_keys(hub)
    page.evaluate(WATCH_STORAGE)
    page.get_by_role("button", name="Add next key · Claude").click()
    field = page.locator("#keys-secret")
    assert field.get_attribute("type") == "password"
    assert field.get_attribute("autocomplete") == "off"
    assert field.get_attribute("spellcheck") == "false"
    assert page.evaluate("document.activeElement.id") == "keys-secret"
    field.fill(SECRET)
    assert field.get_attribute("value") is None  # typed, never written into an attribute
    # a re-render while the field is open keeps the same node (and the typing), without copying the value anywhere
    page.evaluate("document.querySelector('jv-view-keys').draw()")
    assert page.evaluate("document.querySelector('#keys-secret').value") == SECRET
    page.get_by_role("button", name=re.compile("^Check")).click()
    page.wait_for_selector(".jv-keys__row--checking")
    assert len(sent) == 1
    method, path, body = sent[0]
    assert (method, path) == ("POST", "/api/keys/anthropic/next")
    assert json.loads(body) == {"secret": SECRET}
    everything = page.evaluate(EVERYTHING)
    assert SECRET not in everything and PIECE not in everything
    assert page.locator("#keys-secret").count() == 0
    assert page.evaluate("window.__writes") == []
    # the next key shows only its last 4, which the core sends back
    assert LAST4 in page.locator('[data-row="anthropic"]').inner_text()


def test_secret_never_reaches_the_act_endpoint_or_events(hub):
    page = hub.page
    acts = []
    page.on("request", lambda r: acts.append(r.post_data or "") if "/api/act" in r.url else None)
    page, sent, _ = open_keys(hub)
    page.evaluate("window.__acts = []; document.addEventListener('jv-act', e => window.__acts.push(JSON.stringify(e.detail)), true)")
    page.get_by_role("button", name="Add next key · Claude").click()
    page.locator("#keys-secret").fill(SECRET)
    page.keyboard.press("Enter")  # Enter in the field is Check
    page.wait_for_selector(".jv-keys__row--checking")
    assert len(sent) == 1
    assert not any(SECRET in a for a in acts) and not any(SECRET in a for a in page.evaluate("window.__acts"))
    assert SECRET not in json.dumps(page.evaluate("window.__jarvis.store.state.ui.log"))


def test_cancel_and_escape_drop_the_typed_value(hub):
    page, sent, _ = open_keys(hub)
    page.get_by_role("button", name="Add next key · ElevenLabs").click()
    page.locator("#keys-secret").fill(SECRET)
    page.keyboard.press("Escape")
    assert page.locator("#keys-secret").count() == 0
    assert SECRET not in page.evaluate(EVERYTHING)
    assert page.evaluate("document.activeElement.dataset.key") == "add-elevenlabs"
    assert sent == []


def test_rotation_make_live_then_remove_old_with_countdown_and_revoke_link(hub):
    page = hub.scene("keys-next-waiting", theme="night")
    page.wait_for_selector(".jv-keys__row--next_waiting")
    page.evaluate(WATCH_STORAGE)
    page.get_by_role("button", name="Make live · Claude").click()
    claude = page.locator('[data-row="anthropic"]')
    text = claude.inner_text()
    assert "15 more minutes" in text and "in case the new one fails" in text
    link = claude.get_by_role("link", name=re.compile("Revoke it in Claude's console"))
    assert link.get_attribute("href").startswith("https://console.anthropic.com")
    assert link.get_attribute("target") == "_blank" and "noopener" in link.get_attribute("rel")
    assert page.evaluate("document.activeElement.dataset.key") == "remove-old-anthropic"
    page.keyboard.press("Enter")
    assert "kept for" not in claude.inner_text()
    assert claude.get_by_role("link", name=re.compile("Revoke")).count() == 1  # the reminder stays after removing
    assert page.evaluate("window.__writes") == []


def test_scene_preview_add_flow_keeps_nothing(hub):
    page = hub.scene("keys-live", theme="night")
    page.wait_for_selector(".jv-keys__list")
    page.evaluate(WATCH_STORAGE)
    page.get_by_role("button", name="Add next key · Composio").click()
    page.locator("#keys-secret").fill(SECRET)
    page.get_by_role("button", name=re.compile("^Check")).click()
    page.wait_for_selector('[data-row="composio"].jv-keys__row--next_waiting', timeout=4000)
    assert SECRET not in page.evaluate(EVERYTHING) and LAST4 not in page.locator('[data-row="composio"]').inner_text()
    assert page.evaluate("window.__writes") == []


# ---- keyboard and labels ------------------------------------------------------------------------------
def test_keyboard_order_and_labels(hub):
    page, _, _ = open_keys(hub)
    page.locator('[data-key="crumb"]').focus()
    order = []
    for _ in range(9):
        page.keyboard.press("Tab")
        order.append(page.evaluate("document.activeElement.dataset.key"))
    assert order == ["add-anthropic", "remove-anthropic", "add-elevenlabs", "remove-elevenlabs", "add-composio",
                     "remove-composio", "add-restic", "remove-restic", "choose"]
    page.locator('[data-key="add-anthropic"]').focus()
    page.keyboard.press("Enter")
    assert page.evaluate("document.activeElement.id") == "keys-secret"
    assert page.get_by_label("Paste the new Claude key").count() == 1
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.dataset.key") == "check-anthropic"
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.dataset.key") == "cancel-anthropic"
    # every status is a shape + a colour + a word, named for screen readers
    glances = page.locator(".jv-keys__status .jv-glance")
    assert glances.count() == 5
    assert {glances.nth(i).get_attribute("aria-label") for i in range(4)} == {"Live"}
    assert page.locator(".jv-keys__name#name-anthropic").inner_text().startswith("Claude")
    # the remove step asks first, with focus on the safe answer
    page.locator('[data-key="cancel-anthropic"]').click()
    page.get_by_role("button", name="Remove · Claude").click()
    assert page.evaluate("document.activeElement.dataset.key") == "keep-anthropic"
    assert page.get_by_role("group", name=re.compile("Remove the Claude key")).count() == 1


# ---- phone and not connected --------------------------------------------------------------------------
def test_phone_is_view_only(hub):
    page = hub.scene("keys-phone", theme="night")
    page.wait_for_selector(".jv-keys__list")
    assert page.locator(".jv-keys__viewonly").inner_text().startswith("View-only")
    assert page.locator("jv-view-keys button, jv-view-keys input, jv-view-keys select").count() == 0
    assert page.locator(".jv-keys__row").count() == 5


def test_phone_with_a_connected_core_is_view_only_too(hub):
    hub.page.set_viewport_size({"width": 390, "height": 844})
    page, sent, _ = open_keys(hub)
    assert page.evaluate("document.documentElement.dataset.size") == "phone"
    assert page.locator("jv-view-keys button, jv-view-keys input, jv-view-keys select").count() == 0
    assert sent == []


def test_view_only_when_the_core_says_so(hub):
    page, _, _ = open_keys(hub, can_write=False)
    assert page.locator("jv-view-keys input, jv-view-keys select, .jv-keys__actions button").count() == 0


def test_not_connected_on_the_demo_backend_accepts_nothing(hub):
    page = hub.open("#/controls/keys")  # the real demo backend: X-Jarvis-Keys: example
    page.wait_for_selector(".jv-keys__banner")
    assert "Jarvis core isn't connected yet" in page.locator(".jv-keys__banner").text_content()
    page.wait_for_selector(".jv-voice__now:has-text(\"isn't connected\")")
    assert page.locator("jv-view-keys input:enabled, jv-view-keys select, .jv-keys__actions button, .jv-voice button:enabled").count() == 0
    rows = page.locator(".jv-keys__row:not(.jv-keys__row--add)")
    assert rows.count() == 4
    assert page.locator(".jv-keys__ex").count() == 4  # every row is marked as an example
    assert "EX01" in rows.first.inner_text()
    assert [r for r in hub.problems if "/api/keys" in r] == []


def test_not_connected_scene_and_link_from_controls(hub):
    page = hub.scene("controls", theme="night")
    page.get_by_role("link", name="Keys", exact=True).click()
    page.wait_for_selector(".jv-keys__banner")
    page = hub.scene("keys", theme="night")
    page.wait_for_selector(".jv-keys__banner")
    assert page.locator(".jv-keys__actions button").count() == 0


def test_demo_backend_refuses_writes_without_reading_them(hub):
    page = hub.open("#/controls/keys")
    answer = page.evaluate("""async (secret) => { const r = await fetch('/api/keys/anthropic/next', {method: 'POST',
      headers: {'Content-Type': 'application/json'}, body: JSON.stringify({secret})});
      return {status: r.status, header: r.headers.get('X-Jarvis-Keys'), text: await r.text()}; }""", SECRET)
    assert answer["status"] == 200 and answer["header"] == "example"
    assert SECRET not in answer["text"] and json.loads(answer["text"])["error"] == "not_allowed"


# ---- K1 details: a fell-back key raises "Your yes"; restic never shows a last 4 -----------------------------
def test_fell_back_row_raises_a_your_yes_flag(hub):
    page = hub.scene("keys-fell-back", theme="night")
    page.wait_for_selector(".jv-keys__row--fell_back")
    mark = page.locator('[data-row="anthropic"] .jv-keys__status .jv-glance')
    assert mark.get_attribute("data-glance") == "yes" and mark.get_attribute("aria-label") == "Fell back"
    items = page.evaluate("window.__jarvis.store.state.rail.slots.yes.items")
    flag = next(i for i in items if i["ref"] == "keys:anthropic")
    assert flag["state"] == "yes" and flag["title"] == "Claude key fell back"
    js = "import('/views/keys/keys.js').then(m => [m.keysYesFlag({id: 'x', label: 'X (y)', status: 'live'}, 'T'), m.keysYesFlag({id: 'x', label: 'X (y)', status: 'fell_back'}, '2026-11-16T15:40:00').slot])"
    assert page.evaluate(js) == [None, "yes"]


def test_restic_never_shows_a_last4_even_if_one_is_sent(hub):
    page = hub.page
    doc = core_doc()
    restic = next(r for r in doc["rows"] if r["id"] == "restic")
    restic.update(live=slot("PWD9"), next=slot("PWD8"))  # a backend that wrongly sends one
    page.route(re.compile(r".*/api/keys(\?.*)?$"), lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(doc)))
    hub.open("#/controls/keys")
    page.wait_for_selector(".jv-keys__list")
    text = page.locator('[data-row="restic"]').inner_text()
    assert "PWD9" not in text and "PWD8" not in text and "····" not in text and "ending in" not in page.locator('[data-row="restic"]').text_content()
    assert "AAAA" in page.locator('[data-row="anthropic"]').text_content()


# ---- the voice ID (not a secret: shown back, kept on Laptop B) ------------------------------------------
def test_voice_id_is_pasted_saved_and_shown_back(hub):
    page = hub.page
    saved = []

    def settings(route):
        req = route.request
        if req.method == "PUT":
            saved.append(json.loads(req.post_data))
            return route.fulfill(status=200, content_type="application/json", body=json.dumps(saved[-1]))
        return route.fulfill(status=200, content_type="application/json", body=json.dumps({"voice_id": ""}))

    page.route(re.compile(r".*/api/settings(/voice)?$"), settings)
    page, _sent, _doc = open_keys(hub)
    field = page.get_by_label("ElevenLabs voice ID")
    page.wait_for_selector("#voice-id:enabled")
    assert "No voice yet" in page.locator(".jv-voice__now").text_content()
    field.fill("  JBFqnCBsd6RMkjVDRZzb ")
    page.evaluate("document.querySelector('jv-view-keys').draw()")  # a redraw keeps the typing
    assert field.input_value().strip() == "JBFqnCBsd6RMkjVDRZzb"
    page.locator("[data-key='voice-save']").click()
    page.wait_for_selector(".jv-voice__now:has-text('JBFqnCBsd6RMkjVDRZzb')")
    assert saved == [{"voice_id": "JBFqnCBsd6RMkjVDRZzb"}]
    field.fill("nope!")
    page.locator("[data-key='voice-save']").click()
    assert len(saved) == 1  # a malformed ID is caught before anything is sent


# ---- two laptops (v0.24.0): one change can go to both ------------------------------------------------
def two_laptops(page, where):
    """A connected core whose hub says where the keys are kept. Records (step, also-header) for every write."""
    sent, doc = [], core_doc()

    def keys(route):
        req = route.request
        if req.method == "GET":
            return route.fulfill(status=200, headers={"Content-Type": "application/json", **where}, body=json.dumps(doc))
        also = req.headers.get("x-jarvis-also-other")
        sent.append((req.url.rsplit("/", 1)[-1], also))
        doc["rows"][1].update(status="next_waiting", next=slot(LAST4))
        return route.fulfill(status=200, headers={"Content-Type": "application/json", **where, **({"X-Jarvis-Other": "saved"} if also else {})},
                             body=json.dumps(doc["rows"][1]))

    def settings(route):
        req = route.request
        if req.method == "PUT":
            also = req.headers.get("x-jarvis-also-other")
            sent.append(("voice", also))
            return route.fulfill(status=200, headers={"Content-Type": "application/json", **where, **({"X-Jarvis-Other": "unreachable"} if also else {})},
                                 body=req.post_data)
        return route.fulfill(status=200, headers={"Content-Type": "application/json", **where}, body=json.dumps({"voice_id": ""}))

    page.route(re.compile(r".*/api/keys(/.*)?(\?.*)?$"), keys)
    page.route(re.compile(r".*/api/settings(/voice)?$"), settings)
    return sent


def test_a_laptop_with_its_own_jarvis_can_update_the_other_one_too(hub):
    page = hub.page
    sent = two_laptops(page, {"X-Jarvis-Kept": "here", "X-Jarvis-Other-Name": "laptop-b"})
    hub.open("#/controls/keys")
    box = page.get_by_label("Also update laptop-b")
    box.wait_for()
    assert box.is_checked() and "goes to both" in page.locator("#keys-both-hint").text_content()
    assert "on this laptop" in page.locator(".jv-keys__foot").text_content()
    page.get_by_role("button", name="Add next key · ElevenLabs").click()
    page.locator("#keys-secret").fill(SECRET)
    page.get_by_role("button", name="Check the new ElevenLabs key").click()
    page.wait_for_selector("jv-toast:has-text('Same on laptop-b.'), .jv-toast:has-text('Same on laptop-b.')")
    assert sent == [("next", "1")]
    box.uncheck()
    page.evaluate("document.querySelector('jv-view-keys').draw()")  # his choice survives a redraw
    assert not page.get_by_label("Also update laptop-b").is_checked()
    page.wait_for_selector("#voice-id:enabled")
    page.get_by_label("ElevenLabs voice ID").fill("JBFqnCBsd6RMkjVDRZzb")
    page.locator("[data-key='voice-save']").click()
    page.wait_for_selector(".jv-voice__now:has-text('JBFqnCBsd6RMkjVDRZzb')")
    assert sent[-1] == ("voice", None)  # unticked: this laptop only
    page.get_by_label("Also update laptop-b").check()
    page.locator("[data-key='voice-save']").click()
    page.wait_for_selector("jv-toast:has-text(\"laptop-b isn't answering\"), .jv-toast:has-text(\"laptop-b isn't answering\")")
    assert sent[-1] == ("voice", "1")
    assert SECRET not in page.evaluate(EVERYTHING)


def test_a_laptop_using_the_other_jarvis_says_where_the_one_copy_is(hub):
    page = hub.page
    two_laptops(page, {"X-Jarvis-Kept": "laptop-b"})
    hub.open("#/controls/keys")
    page.wait_for_selector(".jv-keys__where:has-text('Kept on laptop-b')")
    assert page.get_by_label("Also update laptop-b").count() == 0  # one Jarvis: nothing to copy to
    assert "on laptop-b" in page.locator(".jv-keys__foot").text_content()
    page.wait_for_selector("[data-kept]:has-text('laptop-b')")


def test_cloud_hearing_is_a_switch_beside_the_voice_and_says_what_leaves_the_laptop(hub):
    page = hub.page
    two_laptops(page, {"X-Jarvis-Kept": "here"})
    acts = []

    def act(route):
        acts.append(json.loads(route.request.post_data))
        route.fulfill(status=200, content_type="application/json", body='{"ok": true}')

    page.route(re.compile(r".*/api/act$"), act)
    hub.open("#/controls/keys")
    switch = page.get_by_role("switch", name="Cloud hearing")
    switch.wait_for()
    assert switch.get_attribute("aria-checked") == "false"
    assert "never leaves it" in page.locator("[data-hear]").text_content()
    switch.click()
    page.wait_for_timeout(300)
    sent = [(a.get("action"), a.get("target"), a.get("args")) for a in acts]
    assert ("set", "cloud_hearing", {"value": True}) in sent or page.evaluate("window.__jarvis.store.state.settings.cloud_hearing") is True
    page.evaluate("""() => { const st = window.__jarvis.store; st.apply({ v: 2, type: "settings.updated", ts: "2026-11-22T21:40:00",
        data: { ...st.state.settings, cloud_hearing: true } }); }""")
    page.wait_for_selector("[data-key='cloud-hearing'][aria-checked='true']")
    assert "leaves the laptop" in page.locator("[data-hear]").text_content()
    assert json.loads(switch.get_attribute("data-args")) == {"value": False}
