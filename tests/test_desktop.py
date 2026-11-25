"""Desktop launcher and packaging files. The native window, PyInstaller and Inno Setup only run on Windows
(GitHub Actions builds them); here we check the parts that can be checked anywhere."""
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import app


def test_page_urls_for_each_mode():
    assert app.page_url("http://127.0.0.1:1", "full") == "http://127.0.0.1:1/"
    assert app.page_url("https://hub.example.ts.net/", "ambient") == "https://hub.example.ts.net/?size=ambient"
    assert app.page_url("http://127.0.0.1:1", "strip").endswith("?size=strip")


def test_flags_that_do_not_fit_together_are_refused():
    with pytest.raises(SystemExit):
        app.main(["--demo", "--hub", "https://hub.example.ts.net"])
    with pytest.raises(SystemExit):
        app.main(["--hub", "not-a-url"])


def test_no_window_mode_serves_the_hub():
    port = app.free_port()
    env = {**os.environ, "JARVIS_DEMO_AUTOPLAY": "0", "NO_PROXY": "*", "no_proxy": "*"}
    proc = subprocess.Popen([sys.executable, str(ROOT / "app.py"), "--no-window", "--port", str(port)],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env, cwd=ROOT)
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        body = None
        for _ in range(100):
            try:
                body = opener.open(f"http://127.0.0.1:{port}/api/health", timeout=1).read().decode()
                break
            except OSError:
                time.sleep(0.1)
        assert body and '"ok":true' in body.replace(" ", "")
        page = opener.open(f"http://127.0.0.1:{port}/", timeout=2).read().decode()
        assert "<jv-tabs" in page
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_packaging_files_agree_with_each_other():
    iss = (ROOT / "installer" / "JarvisHub.iss").read_text(encoding="utf-8")
    release = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    build = (ROOT / "build.ps1").read_text(encoding="utf-8")
    assert "OutputBaseFilename=JarvisHub-Setup" in iss and "dist/JarvisHub-Setup.exe" in release
    assert "PrivilegesRequired=lowest" in iss  # per-user install, no admin password
    for needed in ('--add-data "ui;ui"', '--add-data "contracts;contracts"', '--add-data "VERSION;."', "--name JarvisHub"):
        assert needed in release and needed in build, needed
    # the hub loads threads.py and thumbs.py by name, so PyInstaller can't see them (or PyMuPDF and Pillow behind
    # them) unless it is told: without these the installed reader has no PDFs, question index or page pictures
    for needed in ("--collect-submodules jarvis_hub", "--collect-all pymupdf", "--hidden-import PIL.Image"):
        assert needed in release and needed in build, needed
    assert "/api/file/file-pps7.qindex.json" in release  # the build is checked before it is published
    assert (ROOT / "ui" / "icons" / "app.ico").stat().st_size > 1000
    assert "Download **JarvisHub-Setup.exe** and run it. Python is not needed." in release


def test_canvas_colours_match_the_tokens():
    tokens = (ROOT / "ui" / "tokens.css").read_text(encoding="utf-8")
    assert f"--canvas: {app.CANVAS['day']};" in tokens and f"--canvas: {app.CANVAS['night']};" in tokens


def test_earcons_may_play_without_a_click(monkeypatch):
    """HUD v2 §7: the wake earcon follows his voice, so the window must allow sound with no click first."""
    monkeypatch.setenv("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "--disable-gpu-vsync")
    app.allow_autoplay()
    app.allow_autoplay()  # twice changes nothing
    assert os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] == f"--disable-gpu-vsync {app.AUTOPLAY}"
    assert app.AUTOPLAY == "--autoplay-policy=no-user-gesture-required"
