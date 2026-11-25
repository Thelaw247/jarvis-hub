"""ops/laptop_update.py: the body of "Update Laptop B.bat" and "Start review recording.bat" (v0.16.0). He runs one
file; it puts the newest code where each laptop runs it from, and for the review file switches recording on."""
import importlib.util
import time
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("laptop_update", REPO / "ops" / "laptop_update.py")
up = importlib.util.module_from_spec(spec)
spec.loader.exec_module(up)


def make_zip(path, version, extra=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("VERSION", version + "\n")
        z.writestr("app.py", f"# hub {version}\n")
        z.writestr("jarvis/core/app.py", f"# core {version}\n")
        z.writestr("restart-core.bat", "@echo off\r\n")
        for name, text in (extra or {}).items():
            z.writestr(name, text)
    return path


def laptop_b(tmp_path, version="0.15.3"):
    home = tmp_path / "dewet"
    code, hub = home / "Jarvis", home / "OneDrive" / "Documents" / "JarvisHub"
    for folder in (code, hub):
        (folder / "jarvis" / "core").mkdir(parents=True)
        (folder / "VERSION").write_text(version + "\n")
        (folder / "app.py").write_text("# old\n")
        (folder / "jarvis" / "core" / "app.py").write_text("# old\n")
        (folder / "keep-me.txt").write_text("his own file")
    return home, code, hub


def run(script, home, tmp_path, said, restarted):
    env = {"OneDrive": str(home / "OneDrive"), "JARVIS_ROOT": str(tmp_path / "data")}
    return up.main(script, env=env, home=home, restart=restarted.append, say=said.append, report=lambda code: None)


def test_both_ready_made_files_are_exactly_the_launcher_line_plus_this_body():
    body = (REPO / "ops" / "laptop_update.py").read_text(encoding="ascii")
    for name in ("Update Laptop B.bat", "Start review recording.bat"):
        raw = (REPO / name).read_bytes()
        assert b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"")          # Windows line endings throughout
        first, rest = raw.decode("ascii").replace("\r\n", "\n").split("\n", 1)
        assert rest == body, name
        assert first.startswith("@(if exist ") and first.endswith('-x "%~f0" %*)) & pause & exit /b')
        assert first.count("(") == first.count(")")


def test_on_laptop_b_one_run_updates_both_folders_switches_review_on_and_restarts_the_core(tmp_path):
    home, code, hub = laptop_b(tmp_path)
    make_zip(home / "Downloads" / "_code-0.16.0.zip", "0.16.0")
    said, restarted = [], []
    assert run(home / "Downloads" / "Start review recording.bat", home, tmp_path, said, restarted) == 0
    for folder in (code, hub):
        assert (folder / "VERSION").read_text().strip() == "0.16.0"
        assert (folder / "jarvis" / "core" / "app.py").read_text() == "# core 0.16.0\n"
        assert (folder / "keep-me.txt").read_text() == "his own file"             # nothing is deleted
    assert (hub / "_code-0.16.0.zip").is_file()                                   # OneDrive carries it to Laptop A
    until = float((tmp_path / "data" / "logs" / "review" / "review.on").read_text())
    assert 3.9 * 86400 < until - time.time() < 4.1 * 86400
    assert restarted == [code]
    text = "\n".join(said)
    assert "Review recording is ON until" in text and "v0.15.3 -> v0.16.0" in text and "Close Jarvis Hub" in text


def test_the_plain_update_file_does_not_switch_recording_on(tmp_path):
    home, code, hub = laptop_b(tmp_path)
    make_zip(hub / "_code-0.16.0.zip", "0.16.0")
    said, restarted = [], []
    assert run(hub / "Update Laptop B.bat", home, tmp_path, said, restarted) == 0
    assert (code / "VERSION").read_text().strip() == "0.16.0" and restarted == [code]
    assert not (tmp_path / "data").exists()


def test_on_laptop_a_it_updates_the_hub_and_says_to_run_it_on_laptop_b(tmp_path):
    home, code, hub = laptop_b(tmp_path)
    import shutil
    shutil.rmtree(code)                                                           # Laptop A has no core
    make_zip(home / "Downloads" / "_code-0.16.0.zip", "0.16.0")
    said, restarted = [], []
    assert run(home / "Downloads" / "Start review recording.bat", home, tmp_path, said, restarted) == 0
    assert (hub / "VERSION").read_text().strip() == "0.16.0" and (hub / "_code-0.16.0.zip").is_file()
    assert restarted == [] and not (tmp_path / "data").exists()
    assert "run this same file there" in "\n".join(said)


def test_it_takes_the_highest_version_wherever_it_is(tmp_path):
    home, code, hub = laptop_b(tmp_path)
    make_zip(hub / "_code-0.9.0.zip", "0.9.0")
    make_zip(hub / "_code-0.15.3.zip", "0.15.3")
    make_zip(home / "Downloads" / "_code-0.16.0 (1).zip", "0.16.0")
    (home / "Downloads" / "_code-notes.zip").write_text("not one of ours")
    assert up.newest_zip([hub, home / "Downloads", home / "nowhere"]).name == "_code-0.16.0 (1).zip"
    said, restarted = [], []
    assert run(hub / "Update Laptop B.bat", home, tmp_path, said, restarted) == 0
    assert (code / "VERSION").read_text().strip() == "0.16.0"


def test_nothing_to_install_or_no_jarvis_is_said_in_words_and_changes_nothing(tmp_path):
    home, code, hub = laptop_b(tmp_path)
    said, restarted = [], []
    assert run(hub / "Update Laptop B.bat", home, tmp_path, said, restarted) == 1
    assert "No update file" in said[0] and restarted == [] and (code / "VERSION").read_text().strip() == "0.15.3"
    said.clear()
    assert up.main(tmp_path / "x.bat", env={}, home=tmp_path / "nobody", restart=restarted.append, say=said.append) == 1
    assert "can't find Jarvis" in said[0]


def test_a_zip_that_reaches_outside_the_folder_is_refused(tmp_path):
    home, code, hub = laptop_b(tmp_path)
    make_zip(hub / "_code-0.16.0.zip", "0.16.0", extra={"../outside.txt": "no"})
    said, restarted = [], []
    assert run(hub / "Update Laptop B.bat", home, tmp_path, said, restarted) == 1
    assert not (home / "outside.txt").exists() and not (home / "OneDrive" / "Documents" / "outside.txt").exists()
    assert "didn't finish" in "\n".join(said) and restarted == []
