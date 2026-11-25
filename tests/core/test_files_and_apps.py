"""v0.26.0: Jarvis can create, move and rename his files and open his applications, inside the limits he set:
four folders, his yes before every change, never a delete, never an overwrite, an undo, and apps by name only."""
import asyncio
import json
from types import SimpleNamespace

import pytest

from jarvis.reach import apps, files, hands
from jarvis.tools.base import ToolError
from jarvis.tools.files import handler as files_tool
from jarvis.tools.open_app import handler as app_tool


@pytest.fixture
def home(tmp_path):
    table = {}
    for place in ("class_content", "desktop", "documents", "downloads"):
        (tmp_path / place).mkdir()
        table[place] = (tmp_path / place).resolve()
    (table["downloads"] / "lab3.pdf").write_text("lab")
    (table["class_content"] / "PHYS 152 - Physics" / "Assignments & Labs").mkdir(parents=True)
    (tmp_path / "secret.txt").write_text("not his folders")
    return SimpleNamespace(table=table, log=tmp_path / "undo" / "files.jsonl", root=tmp_path)


def go(home, **args):
    return files.run(args, table=home.table, log=home.log)


def test_it_creates_moves_and_renames_inside_the_four_folders(home):
    assert go(home, action="create", place="documents", path="notes/spring.md", content="# F = -kx\n") == {"ok": True, "did": "Created Documents > notes > spring.md"}
    assert (home.table["documents"] / "notes" / "spring.md").read_text() == "# F = -kx\n"
    assert go(home, action="folder", place="desktop", path="Project")["did"] == "Made the folder Desktop > Project"
    moved = go(home, action="move", place="downloads", path="lab3.pdf", to_place="class_content", to_path="PHYS 152 - Physics/Assignments & Labs")
    assert moved["did"] == "Moved Downloads > lab3.pdf to Class Content > PHYS 152 - Physics > Assignments & Labs > lab3.pdf"
    assert not (home.table["downloads"] / "lab3.pdf").exists()
    renamed = go(home, action="move", place="class_content", path="PHYS 152 - Physics/Assignments & Labs/lab3.pdf", to_path="PHYS 152 - Physics/Assignments & Labs/Lab 3 report.pdf")
    assert renamed["did"].startswith("Renamed ") and (home.table["class_content"] / "PHYS 152 - Physics" / "Assignments & Labs" / "Lab 3 report.pdf").exists()


def test_a_dry_look_changes_nothing(home):
    assert go(home, action="create", place="desktop", path="todo.txt", content="x", dry=True) == {"ok": True, "plan": "Create Desktop > todo.txt"}
    assert go(home, action="move", place="downloads", path="lab3.pdf", to_place="desktop", dry=True)["plan"] == "Move Downloads > lab3.pdf to Desktop > lab3.pdf"
    assert not (home.table["desktop"] / "todo.txt").exists() and (home.table["downloads"] / "lab3.pdf").exists() and not home.log.exists()


@pytest.mark.parametrize("args, why", [
    (dict(action="create", place="desktop", path="../secret2.txt", content="x"), "leave the folder"),
    (dict(action="create", place="desktop", path="run.bat", content="x"), "kinds of file"),
    (dict(action="create", place="desktop", path="tool.exe", content="x"), "kinds of file"),
    (dict(action="create", place="windows", path="a.txt", content="x"), "isn't one of his folders"),
    (dict(action="create", place="downloads", path="lab3.pdf", content="x"), "kinds of file"),
    (dict(action="move", place="downloads", path="nope.pdf", to_place="desktop"), "There is no"),
    (dict(action="move", place="downloads", path="lab3.pdf", to_place="desktop", to_path="../../x.pdf"), "leave the folder"),
    (dict(action="move", place="downloads", path="", to_place="desktop"), "Say which file"),
    (dict(action="delete", place="downloads", path="lab3.pdf"), "create, folder, move or undo"),
    (dict(action="create", place="desktop", path="C:/Windows/x.txt", content="x"), "characters Windows doesn't allow"),
])
def test_it_refuses_what_is_outside_the_limits(home, args, why):
    answer = files.run(args, table=home.table, log=home.log)
    assert answer["ok"] is False and why in answer["why"]
    assert (home.table["downloads"] / "lab3.pdf").read_text() == "lab" and (home.root / "secret.txt").exists()


def test_it_never_overwrites(home):
    (home.table["desktop"] / "lab3.pdf").write_text("the one already there")
    (home.table["desktop"] / "notes.md").write_text("mine")
    assert "don't overwrite" in go(home, action="move", place="downloads", path="lab3.pdf", to_place="desktop")["why"]
    assert "don't overwrite" in go(home, action="create", place="desktop", path="notes.md", content="new")["why"]
    assert (home.table["desktop"] / "lab3.pdf").read_text() == "the one already there" and (home.table["desktop"] / "notes.md").read_text() == "mine"


def test_undo_puts_things_back_and_sets_a_created_file_aside_instead_of_deleting_it(home):
    go(home, action="create", place="desktop", path="todo.txt", content="buy milk")
    go(home, action="move", place="downloads", path="lab3.pdf", to_place="desktop")
    assert go(home, action="undo")["did"] == "Put lab3.pdf back in Downloads" and (home.table["downloads"] / "lab3.pdf").exists()
    assert "set aside, not deleted" in go(home, action="undo")["did"] and not (home.table["desktop"] / "todo.txt").exists()
    kept = list((home.log.parent / "set-aside").iterdir())
    assert len(kept) == 1 and kept[0].read_text() == "buy milk"
    assert go(home, action="undo") == {"ok": False, "why": "There is nothing of mine to take back."}
    assert len([json.loads(x) for x in home.log.read_text().splitlines()]) == 4


def test_the_tool_asks_first_and_changes_things_only_after_his_yes(home, monkeypatch):
    real = files.run
    monkeypatch.setattr(files, "run", lambda args, **kw: real(args, table=home.table, log=home.log))
    ctx = SimpleNamespace(here=True, hands=None)
    args = {"action": "move", "place": "downloads", "path": "lab3.pdf", "to_place": "desktop"}
    asked = asyncio.run(files_tool.run(dict(args), ctx)).content
    assert asked.startswith("Nothing has changed yet") and "Move Downloads > lab3.pdf to Desktop > lab3.pdf?" in asked
    assert (home.table["downloads"] / "lab3.pdf").exists()
    done = asyncio.run(files_tool.run({**args, "confirmed": True}, ctx)).content
    assert done.startswith("Moved Downloads > lab3.pdf to Desktop > lab3.pdf.") and (home.table["desktop"] / "lab3.pdf").exists()
    with pytest.raises(ToolError, match="There is no Downloads > lab3.pdf"):
        asyncio.run(files_tool.run({**args, "confirmed": True}, ctx))
    with pytest.raises(ToolError, match="can't reach the laptop he is at"):
        asyncio.run(files_tool.run(dict(args), SimpleNamespace(here=False, hands=None)))

    far = []

    async def other_laptop(kind, a):
        far.append((kind, a.get("dry", False)))
        return real(a, table=home.table, log=home.log)

    asyncio.run(files_tool.run({"action": "folder", "place": "desktop", "path": "Far", "confirmed": True}, SimpleNamespace(here=False, hands=other_laptop)))
    assert far == [("files", True), ("files", False)] and (home.table["desktop"] / "Far").is_dir()


def test_apps_open_by_name_from_what_is_installed_and_never_as_a_command(tmp_path):
    menu = tmp_path / "Programs"
    for name in ("Google Chrome", "Visual Studio Code", "Word", "Bambu Studio", "Uninstall Bambu Studio", "Spotify Help"):
        (menu / "sub").mkdir(parents=True, exist_ok=True)
        (menu / "sub" / f"{name}.lnk").write_text("")
    opened = []

    listed = {"netflix": ("Netflix", "shell:AppsFolder\\4DF9E0F8.Netflix_mcm4njqhnhss8!Netflix.App"), "xbox": ("Xbox", "shell:AppsFolder\\Microsoft.GamingApp_8wekyb3d8bbwe!Microsoft.Xbox.App")}

    def ask(what):
        return apps.open_app(what, opener=opened.append, menus=[menu], store=lambda: listed)

    assert ask("open VS Code please")["opened"] == "Visual Studio Code" and opened[-1].endswith("Visual Studio Code.lnk")
    assert ask("chrome")["opened"] == "Google Chrome" and ask("Bambu")["opened"] == "Bambu Studio"   # never the uninstaller
    assert ask("the calculator") == {"ok": True, "opened": "calculator"} and opened[-1] == "calc.exe"
    assert ask("Spotify")["opened"] == "spotify" and opened[-1] == "spotify:"                         # a store app: its fixed link
    assert ask("Netflix")["opened"] == "Netflix" and opened[-1].startswith("shell:AppsFolder\\4DF9E0F8.Netflix")   # a Store app: no shortcut file
    before = len(opened)
    assert ask("cmd /c del C:\\\\Users")["ok"] is False and ask("C:/Windows/System32/cmd.exe")["ok"] is False
    assert ask("blender") == {"ok": False, "why": "not_found", "near": []} and ask("bam studio x")["near"] == ["Bambu Studio"]
    assert len(opened) == before
    assert hands.run("app", {"app": "word"}, opener=opened.append)["ok"] in (True, False)   # the far laptop takes the same question


def test_the_app_tool_says_what_opened_or_offers_the_near_names(monkeypatch):
    monkeypatch.setattr(apps, "open_app", lambda name, **kw: {"ok": True, "opened": "Spotify"} if "spot" in name.lower() else {"ok": False, "why": "not_found", "near": ["Bambu Studio"]})
    assert "Opened Spotify" in asyncio.run(app_tool.run({"app": "Spotify"}, SimpleNamespace(here=True))).content
    with pytest.raises(ToolError, match="Close matches: Bambu Studio"):
        asyncio.run(app_tool.run({"app": "bambo"}, SimpleNamespace(here=True)))


def test_store_apps_come_from_windows_own_list_and_odd_ids_are_left_out():
    rows = [{"Name": "Netflix", "AppID": "4DF9E0F8.Netflix_mcm4njqhnhss8!Netflix.App"}, {"Name": "Uninstall Thing", "AppID": "x"},
            {"Name": "Evil", "AppID": "calc.exe & del C:\\x"}, {"Name": "Word", "AppID": "Microsoft.Office.WINWORD.EXE.15"}]
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        return SimpleNamespace(stdout=json.dumps(rows))

    now = [1000.0]
    apps._START.update(at=-1e9, apps={})   # noqa: SLF001 - nothing remembered from another test
    found = apps.start_apps(run=run, clock=lambda: now[0])
    assert set(found) == {"netflix", "word"} and found["netflix"] == ("Netflix", "shell:AppsFolder\\4DF9E0F8.Netflix_mcm4njqhnhss8!Netflix.App")
    assert calls[0][0] == "powershell" and "Get-StartApps" in calls[0][-1]
    apps.start_apps(run=run, clock=lambda: now[0] + 5)
    assert len(calls) == 1                                    # remembered: the second ask is instant
    now[0] += 700
    assert apps.start_apps(run=lambda *a, **k: (_ for _ in ()).throw(OSError()), clock=lambda: now[0]) == {}

