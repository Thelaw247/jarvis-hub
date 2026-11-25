"""v0.15.0: one icon. The hub runs this laptop's voice itself, and never takes it from another laptop unasked."""
import json
import sys
import textwrap
import time
from pathlib import Path

import jsonschema
from fastapi.testclient import TestClient

from jarvis_hub import voicehost
from jarvis_hub.server import create_app
from jarvis_hub.voicehost import VoiceHost

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / "contracts" / "voice_host.schema.json").read_text(encoding="utf-8"))

# a stand-in for the voice program: another laptop has the voice until the hub says "take"; it leaves with its hub
CHILD = textwrap.dedent("""
    import sys
    print("  Mic: boost (its own chatter is ignored)", flush=True)
    print("@@ waiting laptop-b", flush=True)
    for line in sys.stdin:
        if line.strip() == "take":
            print("@@ live", flush=True)
    open(sys.argv[1], "w").write("left with the hub")
""")


def wait_for(check, seconds=5.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if check():
            return True
        time.sleep(0.02)
    return False


def host(tmp_path, monkeypatch, code=CHILD, **kw):
    monkeypatch.setenv("JARVIS_CORE_SESSION", "tok")
    monkeypatch.delenv("JARVIS_HUB_VOICE", raising=False)
    return VoiceHost(tmp_path, command=[sys.executable, "-u", "-c", code, str(tmp_path / "left.txt")], **kw)


def test_it_waits_its_turn_takes_the_voice_when_asked_and_leaves_with_the_hub(tmp_path, monkeypatch):
    h = host(tmp_path, monkeypatch)
    assert h.start()
    assert wait_for(lambda: h.state == "waiting")
    assert h.status() == {"state": "waiting", "device": "laptop-b", "message": ""}
    jsonschema.validate(h.status(), SCHEMA)
    assert h.take()                                       # "Talk here"
    assert wait_for(lambda: h.state == "live")
    jsonschema.validate(h.status(), SCHEMA)
    h.stop()                                              # the hub closes
    assert wait_for(lambda: (tmp_path / "left.txt").exists())   # the voice program stopped by itself
    assert h.state == "off"


def test_what_the_hidden_voice_program_does_is_kept_in_a_log(tmp_path, monkeypatch):
    (tmp_path / "logs").mkdir()
    monkeypatch.setenv("JARVIS_ROOT", str(tmp_path))
    h = host(tmp_path, monkeypatch)
    assert h.start() and wait_for(lambda: h.state == "waiting")
    assert h.take() and wait_for(lambda: h.state == "live")
    h.stop()
    log = tmp_path / "logs" / "voice-host.log"
    assert wait_for(lambda: "ended" in log.read_text(encoding="utf-8"))
    lines = [line.split(" ", 2)[2] for line in log.read_text(encoding="utf-8").splitlines()]
    assert lines[0].startswith("hub: started the voice program with python")
    for want in ("Mic: boost (its own chatter is ignored)", "@@ waiting laptop-b", "hub: voice is waiting laptop-b",
                 "hub: Talk here", "@@ live", "hub: voice is live", "hub: the voice program ended (code 0)"):
        assert any(want in line for line in lines), (want, lines)


def test_no_logs_folder_means_no_log_and_no_error(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_ROOT", str(tmp_path / "nowhere"))
    voicehost.note("hello")
    assert not (tmp_path / "nowhere").exists()


def test_a_voice_program_that_dies_is_started_again(tmp_path, monkeypatch):
    marker = tmp_path / "runs.txt"
    code = textwrap.dedent(f"""
        import sys
        p = {str(marker)!r}
        n = len(open(p).read()) if __import__("os").path.exists(p) else 0
        open(p, "a").write("x")
        if n == 0:
            print("@@ live", flush=True)
            sys.exit(3)                                   # crashes the first time
        print("@@ live", flush=True)
        sys.stdin.read()
    """)
    h = host(tmp_path, monkeypatch, code=code, restart_s=(0.05,))
    h.start()
    assert wait_for(lambda: marker.exists() and len(marker.read_text()) == 2)
    assert wait_for(lambda: h.state == "live")
    h.stop()


def test_it_says_in_words_what_is_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("JARVIS_CORE_SESSION", raising=False)
    h = VoiceHost(tmp_path)
    assert not h.start() and "isn't paired" in h.status()["message"]
    monkeypatch.setenv("JARVIS_CORE_SESSION", "tok")
    monkeypatch.setenv("JARVIS_HUB_VOICE", "0")
    assert not h.start() and h.status()["state"] == "off"
    monkeypatch.delenv("JARVIS_HUB_VOICE")
    monkeypatch.setattr(voicehost, "voice_python", lambda root: None)
    assert not h.start() and "isn't installed" in h.status()["message"]
    jsonschema.validate(h.status(), SCHEMA)
    unpaired = host(tmp_path, monkeypatch, code='print("@@ off not_paired", flush=True)', restart_s=(0.01,))
    unpaired.start()
    assert wait_for(lambda: unpaired.state == "off" and unpaired.reason == "not_paired")
    time.sleep(0.2)
    assert unpaired.state == "off"                        # not restarted: a restart wouldn't fix it


def test_the_hub_serves_its_voice_state_and_talk_here(tmp_path, monkeypatch):
    app = create_app(demo=True, autoplay=False, speed=0)
    with TestClient(app, base_url="http://127.0.0.1") as c:
        off = c.get("/api/voicehost").json()
        jsonschema.validate(off, SCHEMA)
        assert off["state"] == "off" and "demo" in off["message"].lower()
        assert c.post("/api/voicehost/take").json() == {"ok": False}
        h = host(tmp_path, monkeypatch)
        app.state.voicehost = h
        h.start()
        assert wait_for(lambda: c.get("/api/voicehost").json()["state"] == "waiting")
        assert c.get("/api/voicehost").json()["device"] == "laptop-b"
        assert c.post("/api/voicehost/take", headers={"Origin": "http://evil.example"}).status_code == 403
        assert c.post("/api/voicehost/take").json() == {"ok": True}
        assert wait_for(lambda: c.get("/api/voicehost").json()["state"] == "live")
        h.stop()


def test_the_voice_program_runs_on_a_python_that_has_the_sound_packages(tmp_path, monkeypatch):
    exe = voicehost.voice_python(tmp_path)
    assert exe is None or Path(exe).name.lower().startswith("python")
    monkeypatch.setattr(voicehost.importlib.util, "find_spec", lambda name: None)       # the hub's Python lacks them
    core = tmp_path / "JarvisCore" / "venv" / "Scripts"
    core.mkdir(parents=True)
    (core / "python.exe").write_text("")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert voicehost.voice_python(tmp_path) == str(core / "python.exe")                 # Laptop B: the core's
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "nowhere"))
    assert voicehost.voice_python(tmp_path) is None


def test_not_connected_comes_with_the_voice_programs_own_reason(tmp_path, monkeypatch):
    """22 Nov: Laptop A ran its own Jarvis with no voice ID. The hub said only "Not connected", so it looked like a
    network fault; the reason was sitting in the voice program's output the whole time."""
    code = ('import time\nprint("@@ down error", flush=True)\n'
            'print("  No voice yet: paste the ElevenLabs voice ID in Controls › Keys › Voice. Trying again in 2 s.", flush=True)\n'
            'time.sleep(0.4)\nprint("@@ live", flush=True)\ntime.sleep(5)')
    h = host(tmp_path, monkeypatch, code=code)
    h.start()
    assert wait_for(lambda: h.status()["message"].startswith("No voice yet: paste the ElevenLabs voice ID"))
    assert h.status()["state"] == "down" and "Trying again" not in h.status()["message"]
    jsonschema.validate(h.status(), SCHEMA)
    assert wait_for(lambda: h.state == "live") and h.status()["message"] == ""   # and it is forgotten once it works
    h.stop()

