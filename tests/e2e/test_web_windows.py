"""Web windows (R1, REACH §5.1) in a real browser: a live page in the glass frame, a tabs window, the card for
pages that can't be framed, full size on the Stage, and the sandbox. The component is imported straight into a
scene page, so these run before the overseer wires the kind into the board (see the last test)."""
import pytest

SETUP = """async () => {
  await import('/components/web-frame/web-frame.js');
  window.__opened = [];
  window.open = (url, target, features) => { window.__opened.push([url, target, features]); return null; };
  window.__web = (pages, opts = {}) => {
    document.querySelector('#web-host')?.remove();
    const host = Object.assign(document.createElement('div'), { id: 'web-host' });
    host.style.cssText = 'position:fixed;left:0;top:0;width:600px;z-index:1';
    const frame = document.createElement('jv-web-frame');
    Object.assign(frame, opts);
    frame.win = { id: 'w-web-test', type: 'web', title: 'Test', data: { pages } };
    host.append(frame);
    document.body.append(host);
    return frame;
  };
}"""
ORIGIN_PAGE = "/demo/web/search.html?q=method+of+joints"


@pytest.fixture
def web(hub):
    hub.scene("component:window", theme="night")
    hub.page.evaluate(SETUP)
    return hub


def page(id_, url, title, **more):
    return {"id": id_, "url": url, "title": title, **more}


def mode(hub, page_id):
    return hub.page.evaluate(f"() => document.querySelector('#web-host jv-web-frame').state['{page_id}']")


def test_the_web_kind_registers_as_media_on_the_board(web):
    kind = web.page.evaluate("""() => import('/core/window-kinds.js').then(m => { const k = m.windowKind('web');
        return { role: k.role, width: k.width, size: k.size, tag: k.content({ id: 'w', type: 'web', data: { pages: [] } }).tagName }; })""")
    assert kind == {"role": "media", "width": 600, "size": "2x2", "tag": "JV-WEB-FRAME"}


def test_only_http_and_https_pages_are_ever_shown(web):
    out = web.page.evaluate("""() => import('/components/web-frame/web-policy.js').then(m => [
        ['javascript:alert(1)', 'data:text/html,hi', 'file:///C:/x.html', 'blob:http://x/1', 'about:blank', 'https://me:pw@example.com/', 'ftp://x.org/', ' '].map(m.safeUrl),
        m.safeUrl('https://www.google.com/search?q=a b'),
        m.pagesOf({ data: { pages: [{ id: 'a', url: 'javascript:alert(1)', title: 'x' }, { id: 'b', url: 'http://example.com', title: 'ok' }] } }).pages.map(p => p.id)])""")
    assert out[0] == [None] * 8
    assert out[1].startswith("https://www.google.com/search?q=a")
    assert out[2] == ["b"]
    frame = web.page.evaluate("() => { const f = window.__web([{ id: 'x', url: 'javascript:alert(1)', title: 'x' }]); return f.textContent; }")
    assert frame == "That page can't be shown here."
    assert web.page.locator("#web-host iframe").count() == 0


def test_a_live_page_loads_in_a_sandbox_that_cannot_reach_the_hub(web):
    web.page.evaluate(f"() => window.__web([{{ id: 'p-search', url: location.origin + '{ORIGIN_PAGE}', title: 'method of joints - Search' }}])")
    web.page.wait_for_function("() => document.querySelector('#web-host jv-web-frame').state['p-search'] === 'loaded'")
    frame = web.page.locator("#web-host iframe")
    assert frame.get_attribute("title") == "method of joints - Search"
    # the hub's own address: no same-origin, so the page gets an opaque origin; never top navigation or pop-ups
    assert frame.get_attribute("sandbox") == "allow-scripts allow-forms"
    assert frame.get_attribute("allow") == "" and frame.get_attribute("referrerpolicy") == "no-referrer"
    reach = web.page.evaluate("""() => { const f = document.querySelector('#web-host iframe');
        let doc = 'readable'; try { doc = f.contentDocument === null ? 'null' : 'readable'; } catch { doc = 'blocked'; }
        let bridge = 'none'; try { bridge = typeof f.contentWindow.__jarvis; } catch { bridge = 'blocked'; } return [doc, bridge]; }""")
    assert reach[0] in ("null", "blocked") and reach[1] in ("blocked", "undefined")
    other = web.page.evaluate("() => import('/components/web-frame/web-policy.js').then(m => m.sandboxFor('https://example.com/', location.origin))")
    assert other == "allow-scripts allow-same-origin allow-forms"
    assert "top-navigation" not in other and "popups" not in other


def test_a_tabs_window_has_a_real_tablist_and_keeps_each_page(web):
    web.page.evaluate(f"""() => window.__web([
        {{ id: 'p-article', url: location.origin + '/demo/web/article.html', title: 'The method of joints, step by step' }},
        {{ id: 'p-search', url: location.origin + '{ORIGIN_PAGE}', title: 'method of joints - Search' }},
        {{ id: 'p-doc', url: 'https://docs.google.com/document/d/x/edit', title: 'GE 122 lab notes', frame: 'no' }}])""")
    tabs = web.page.locator("#web-host [role=tab]")
    assert tabs.count() == 3 and tabs.nth(0).get_attribute("aria-selected") == "true"
    assert web.page.locator("#web-host [role=tablist]").get_attribute("aria-label") == "Pages"
    assert [tabs.nth(i).get_attribute("tabindex") for i in range(3)] == ["0", "-1", "-1"]
    assert web.page.locator("#web-host iframe").count() == 1  # only the shown page is made
    tabs.nth(0).focus()
    web.page.keyboard.press("ArrowRight")
    assert tabs.nth(1).get_attribute("aria-selected") == "true" and web.page.evaluate("() => document.activeElement.textContent") == "method of joints - Search"
    assert web.page.locator("#web-host iframe").count() == 2
    web.page.keyboard.press("End")
    assert tabs.nth(2).get_attribute("aria-selected") == "true"
    panel = web.page.locator("#web-host .jv-web__page:not([hidden])")
    assert panel.get_attribute("data-mode") == "card" and panel.get_attribute("aria-labelledby") == tabs.nth(2).get_attribute("id")
    web.page.keyboard.press("Home")
    assert web.page.locator("#web-host iframe").count() == 2  # pages already made are kept: switching back is instant


def test_a_page_that_cannot_be_framed_becomes_a_card_that_opens_the_browser(web):
    web.page.evaluate("() => window.__web([{ id: 'p-doc', url: 'https://docs.google.com/document/d/demo/edit', title: 'GE 122 lab notes', site: 'docs.google.com' }], { desktop: false })")
    card = web.page.locator("#web-host .jv-web__card")
    assert card.locator(".jv-web__title").text_content() == "GE 122 lab notes"
    assert card.locator(".jv-web__address").text_content() == "docs.google.com/document/d/demo/edit"
    assert web.page.locator("#web-host iframe").count() == 0  # known to refuse framing in a browser: no broken frame
    opener = web.page.locator("#web-host [data-key=open]")
    assert opener.text_content() == "Open in browser: GE 122 lab notes"
    opener.click()
    assert web.page.evaluate("() => window.__opened") == [["https://docs.google.com/document/d/demo/edit", "_blank", "noopener,noreferrer"]]
    # on the desktop app WebView2 frames it (jarvis_hub/webframes.py), so the same page is tried live there
    web.page.evaluate("() => window.__web([{ id: 'p-doc', url: 'https://docs.google.com/document/d/demo/edit', title: 'GE 122 lab notes' }], { desktop: true })")
    assert web.page.locator("#web-host iframe").count() == 1
    assert web.page.locator("#web-host iframe").get_attribute("sandbox") == "allow-scripts allow-same-origin allow-forms"


def test_a_load_error_or_a_timeout_shows_the_card(web):
    web.page.evaluate(f"() => window.__web([{{ id: 'slow', url: location.origin + '{ORIGIN_PAGE}', title: 'Slow page' }}], {{ timeout: 1 }})")
    web.page.wait_for_function("() => document.querySelector('#web-host jv-web-frame').state.slow === 'card'")
    assert web.page.locator("#web-host .jv-web__page").get_attribute("data-why") == "timeout"
    web.page.evaluate(f"() => window.__web([{{ id: 'bad', url: location.origin + '{ORIGIN_PAGE}', title: 'Broken page' }}], {{ timeout: 60000 }})")
    web.page.evaluate("() => document.querySelector('#web-host iframe').dispatchEvent(new Event('error'))")
    assert mode(web, "bad") == "card" and web.page.locator("#web-host .jv-web__page").get_attribute("data-why") == "error"


def test_activating_a_live_page_opens_it_full_size_and_esc_brings_focus_back(web):
    web.page.evaluate(f"""() => window.__web([
        {{ id: 'p-article', url: location.origin + '/demo/web/article.html', title: 'The method of joints, step by step' }},
        {{ id: 'p-search', url: location.origin + '{ORIGIN_PAGE}', title: 'method of joints - Search' }}])""")
    opener = web.page.locator("#web-host [data-key=open]")
    assert opener.text_content().startswith("Open full size")
    opener.click()
    full = web.page.locator("jv-web-full")
    assert full.get_attribute("role") == "dialog" and full.get_attribute("aria-modal") == "true"
    assert full.locator(".jv-web-full__kicker").text_content() == "Web // 127.0.0.1"  # no site given: the host
    assert full.locator(".jv-web-full__index").text_content() == "01 / 02"
    assert web.page.evaluate("() => document.activeElement.dataset.key") == "close"
    path = web.page.evaluate("() => location.hash")
    web.page.keyboard.press("1")  # the hub's shortcuts don't apply while a page is open
    assert web.page.evaluate("() => location.hash") == path
    full.locator("[role=tab]").nth(1).click()
    assert full.locator(".jv-web-full__index").text_content() == "02 / 02"
    full.locator("[data-key=browser]").click()
    assert web.page.evaluate("() => window.__opened.at(-1)[0]").endswith(ORIGIN_PAGE)
    web.page.keyboard.press("Escape")
    assert web.page.locator("jv-web-full").count() == 0
    assert web.page.evaluate("() => document.activeElement.dataset.key") == "open"
    assert web.problems == []


def test_on_the_board_the_kicker_reads_web_site_and_follows_the_tab(web):
    web.page.evaluate("""() => { const win = { id: 'w-tabs', type: 'web', title: 'Reading', data: { pages: [
        { id: 'a', url: 'https://docs.google.com/a', title: 'A', frame: 'no' }, { id: 'b', url: 'https://example.com/b', title: 'B', frame: 'no' }] } };
      const w = document.createElement('jv-window');
      w.setAttribute('heading', 'Web'); w.setAttribute('status', 'docs.google.com'); w.setAttribute('index', '01 / 02');
      w.setAttribute('window-id', 'w-tabs'); w.setAttribute('opens', ''); w.setAttribute('media', '');
      const f = document.createElement('jv-web-frame'); f.win = win; w.append(f); document.body.append(w); }""")
    win = web.page.locator("jv-window[window-id=w-tabs]")
    assert win.locator(".jv-window__title").text_content().replace("\u00a0", " ").strip().endswith("Web // docs.google.com")
    win.locator("[role=tab]").nth(1).click()
    assert win.get_attribute("status") == "example.com" and win.get_attribute("index") == "02 / 02"
    kicker = web.page.evaluate("() => import('/core/window-kinds.js').then(m => m.windowKind('web').kicker({ id: 'w-tabs', data: { pages: [{ id: 'a', url: 'https://docs.google.com/a', title: 'A' }, { id: 'b', url: 'https://example.com/b', title: 'B' }] } }))")
    assert kicker == {"heading": "Web", "status": "example.com", "index": "02 / 02"}  # a redraw keeps his tab
    # the whole panel is its "Open it": a click on the card (not a tab) opens the shown page in the browser
    win.locator(".jv-web__page:not([hidden]) .jv-web__card").click()
    assert web.page.evaluate("() => window.__opened.at(-1)[0]") == "https://example.com/b"


def test_the_board_draws_web_windows_once_the_kind_is_wired(web):
    """The overseer's hook (v0.5.0): views/now/widgets.js and core/windows.js ask core/window-kinds.js first."""
    tag = web.page.evaluate("""() => import('/views/now/widgets.js').then(m => m.windowContent(
        { id: 'w', type: 'web', title: 'Web', data: { pages: [{ id: 'a', url: 'https://example.com/', title: 'A' }] } },
        window.__jarvis.store.state, new Date()).tagName)""")
    if tag != "JV-WEB-FRAME":
        pytest.skip("The web window kind isn't wired into the board yet (overseer hook, see R1 report).")
    role = web.page.evaluate("() => import('/core/windows.js').then(m => [m.roleOf({ type: 'web' }), m.tierOf({ type: 'web' }), m.panelWidth({ type: 'web' }, 1840)])")
    assert role == ["media", "L", 600]  # the L tier at 1920 (v0.4.1's tiers), from the one window-kind registry


def test_a_sign_in_page_is_a_card_even_in_the_desktop_app(web):
    """2026-11-19: Composio's site in a hub window ended on Google's "403: you do not have access to this page"."""
    modes = web.page.evaluate("""() => import('/components/web-frame/web-policy.js').then(m => [
        'https://accounts.google.com/o/oauth2/auth', 'https://platform.composio.dev/', 'https://connect.composio.dev/link/lk_1',
        'https://login.microsoftonline.com/common', 'https://www.google.com/search?q=x', 'https://en.wikipedia.org/wiki/X',
      ].map(url => m.frameMode({ url }, { desktop: true })))""")
    assert modes == ["card", "card", "card", "card", "frame", "frame"]
