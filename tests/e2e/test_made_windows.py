"""v0.23.0: a window Jarvis made loads from the hub's own address, in the strict sandbox, and is titled as his."""


def test_a_made_page_is_framed_from_the_hub_itself_with_no_same_origin(hub):
    page = hub.scene("now-active")
    got = page.evaluate("""import('/components/web-frame/web-policy.js').then(m => {
      const made = 'http://jarvis.made/0123456789ab', src = m.frameSrc(made, location.origin, 'day');
      return [m.isMade(made), m.isMade('https://example.com/'), src.replace(location.origin, ''), m.sandboxFor(src, location.origin),
              m.frameSrc('https://example.com/a', location.origin), m.frameSrc('http://jarvis.made/../../api/state', location.origin).startsWith(location.origin),   // never a way into the hub's own doors
              m.frameMode({ url: made }), m.webKicker({ data: { pages: [{ id: 'p-1', url: made, title: 'Period of a spring' }] } })];
    })""")
    assert got[:6] == [True, False, "/api/made/0123456789ab?theme=day", "allow-scripts allow-forms", "https://example.com/a", False]
    assert got[6] == "frame" and got[7] == {"heading": "Jarvis", "status": "Period of a spring", "index": ""}
    page.evaluate("""window.__jarvis.store.apply({ type: 'window.push', ts: window.__jarvis.store.state.now, data: {
      id: 'w-made-0123456789ab', type: 'web', title: 'Period of a spring', size: '2x2',
      data: { pages: [{ id: 'p-0123456789ab', url: 'http://jarvis.made/0123456789ab', title: 'Period of a spring' }], active: 'p-0123456789ab' } } })""")
    frame = page.locator('jv-window[window-id="w-made-0123456789ab"] iframe')
    frame.wait_for(state="attached")
    assert frame.get_attribute("src").endswith("/api/made/0123456789ab?theme=day") or "/api/made/0123456789ab?theme=" in frame.get_attribute("src")
    assert frame.get_attribute("sandbox") == "allow-scripts allow-forms"
