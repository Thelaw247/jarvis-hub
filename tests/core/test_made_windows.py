"""v0.23.0: Jarvis writes a page himself and it shows as a hub window, sandboxed like a stranger's web page."""
import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from jarvis.core.app import create_app
from jarvis.core.config import Config
from jarvis.core.sessions import HubSessions
from jarvis.reach import made
from jarvis.tools.base import ToolError
from jarvis.tools.make_window import handler

BODY = "<h2>Period of a spring</h2><ol><li>k = mg/x</li><li>T = 2&pi;&radic;(m/k)</li></ol><script>document.title='x'</script>"


def test_the_tool_keeps_the_page_and_pushes_a_window_that_points_at_it(tmp_path):
    out = asyncio.run(handler.run({"title": "Period of  a spring", "html": BODY, "size": "3x2"}, SimpleNamespace(root=tmp_path)))
    kind, window = out.show
    page = window["data"]["pages"][0]
    assert kind == "window.push" and window["type"] == "web" and window["title"] == "Period of a spring" and window["size"] == "3x2"
    assert page["url"].startswith("http://jarvis.made/") and window["data"]["active"] == page["id"]
    made_id = page["url"].rsplit("/", 1)[-1]
    assert made.load(tmp_path, made_id)["body"] == BODY and "don't read it out" in out.content
    for bad in ({"title": "x"}, {"title": "x", "html": "<html><body>hi</body></html>"}, {"title": "x", "html": "y" * (made.MAX_BODY + 1)}):
        with pytest.raises(ToolError):
            asyncio.run(handler.run(bad, SimpleNamespace(root=tmp_path)))
    warned = asyncio.run(handler.run({"title": "x", "html": '<img src="https://example.com/a.png">'}, SimpleNamespace(root=tmp_path)))
    assert "will not load" in warned.content
    assert made.load(tmp_path, "../../etc/passwd") is None and made.load(tmp_path, "zzzzzzzzzzzz") is None


def test_only_the_newest_pages_are_kept(tmp_path, monkeypatch):
    monkeypatch.setattr(made, "KEEP", 3)
    ids = [made.save(tmp_path, f"t{i}", f"<p>{i}</p>") for i in range(5)]
    assert len(list(made.folder(tmp_path).glob("*.json"))) == 3 and made.load(tmp_path, ids[-1])["title"] == "t4"


def test_the_core_serves_it_to_his_screens_only_and_locked_down(tmp_path):
    config = Config.from_env({}, root=tmp_path / "Jarvis", extra_hosts=("testserver",), keystore="memory", voice_preload=False, hub_feed=False)
    app = create_app(config, log_to_stderr=False)
    token = HubSessions(config.data_dir / "hub_sessions.json").pair("test-hub")
    made_id = made.save(config.root, "Period of a spring", BODY)
    with TestClient(app) as client:
        assert client.get(f"/api/made/{made_id}").status_code == 401                     # a stranger on the network gets nothing
        ok = client.get(f"/api/made/{made_id}?theme=day", headers={"X-Jarvis-Session": token})
        assert ok.status_code == 200 and BODY in ok.text and 'data-theme="day"' in ok.text
        csp = ok.headers["content-security-policy"]
        assert csp.startswith("sandbox allow-scripts allow-forms;") and "allow-same-origin" not in csp     # no origin: it cannot reach the hub
        assert "default-src 'none'" in csp and "connect-src" not in csp and ok.headers["x-content-type-options"] == "nosniff"
        assert "--bg-0" in ok.text and "var(--text)" in ok.text                         # the hub's own colours, none named here
        assert client.get("/api/made/aaaaaaaaaaaa", headers={"X-Jarvis-Session": token}).status_code == 404
    assert "#" not in made.BASE                                                          # hex colours live only in ui/tokens.css


def test_the_hub_passes_it_through_with_the_sandbox_policy_set_again():
    src = open("jarvis_hub/live.py", encoding="utf-8").read()
    assert '@router.get("/api/made/{made_id}")' in src and src.count("headers=HEADERS") >= 4
    from jarvis.tools.voice import ROUTING

    assert "make_window" in ROUTING and "don't read it out" in ROUTING
