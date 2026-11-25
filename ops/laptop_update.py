# Jarvis: put the newest code on this laptop, and (when this file's name says "review") switch review recording on.
#
# This is the body of "Update Laptop B.bat" and "Start review recording.bat": each of those is this file with one
# launcher line on top (python -x skips it), so the logic is plain Python that the tests run, not batch.
# Standard library only. Nothing is deleted. C:\Jarvis (memory, keys, logs) is only touched to write the one small
# file that switches review recording on.
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

REVIEW_DAYS = 4.0
NAME = re.compile(r"^_code-(\d+)\.(\d+)\.(\d+)(?: \(\d+\))?\.zip$")     # "_code-0.16.0.zip", or a browser's " (1)" copy


def newest_zip(folders):
    """The highest-numbered _code-x.y.z.zip in these folders (newest file wins a tie), or None."""
    found = []
    for folder in folders:
        try:
            for p in Path(folder).iterdir():
                m = NAME.match(p.name)
                if m and p.is_file():
                    found.append((tuple(int(x) for x in m.groups()), p.stat().st_mtime, p))
        except OSError:
            continue
    return max(found)[2] if found else None


def version_of(folder):
    try:
        return (Path(folder) / "VERSION").read_text(encoding="ascii").strip()
    except OSError:
        return ""


def unpack(zip_path, target):
    """Write every file in the zip that differs from what is there. Returns how many were written."""
    target = Path(target)
    written = 0
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            name = info.filename
            parts = Path(name).parts
            if name.startswith(("/", "\\")) or ".." in parts or ":" in name:
                raise ValueError(f"The update file has a path that doesn't belong in it: {name}")
            dest = target.joinpath(*parts)
            if info.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
                continue
            data = z.read(info)
            try:
                if dest.read_bytes() == data:
                    continue
            except OSError:
                pass
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            written += 1
    return written


def review_on(root, days=REVIEW_DAYS, now=None):
    until = (now if now is not None else time.time()) + days * 86400
    flag = Path(root) / "logs" / "review" / "review.on"
    flag.parent.mkdir(parents=True, exist_ok=True)
    flag.write_text(str(int(until)), encoding="ascii")
    return until


def main(script, env=None, home=None, restart=None, say=print, report=None):
    env = os.environ if env is None else env
    home = Path(home or Path.home())
    script = Path(script)
    here = script.resolve().parent
    review = "review" in script.name.lower()
    code = home / "Jarvis"
    hub = Path(env.get("OneDrive") or home / "OneDrive") / "Documents" / "JarvisHub"
    is_core = (code / "jarvis" / "core" / "app.py").is_file()
    has_hub = (hub / "app.py").is_file()
    if not is_core and not has_hub:
        say("I can't find Jarvis on this laptop (no Jarvis folder, and no JarvisHub folder in OneDrive > Documents).")
        return 1
    zip_path = newest_zip([here, home / "Downloads", hub])
    if zip_path is None:
        say("No update file (_code-x.y.z.zip) found next to this file, in Downloads, or in OneDrive > Documents >")
        say("JarvisHub. If OneDrive is still syncing, wait a minute and run this again.")
        return 1
    new = ".".join(NAME.match(zip_path.name).groups())
    say(f"Update file: {zip_path.name}")
    try:
        for label, folder, there in (("Jarvis core (this laptop)", code, is_core), ("Jarvis Hub (shared by OneDrive)", hub, has_hub)):
            if not there:
                continue
            before = version_of(folder)
            n = unpack(zip_path, folder)
            say(f"  {label}: v{before or '?'} -> v{version_of(folder)} ({n} files changed)")
            if version_of(folder) != new:
                say(f"  That folder says v{version_of(folder)}, not v{new}. Run this again; if it repeats, tell Claude.")
                return 1
        if has_hub and zip_path.parent != hub:
            with_hub = hub / f"_code-{new}.zip"
            if not with_hub.exists():
                shutil.copyfile(zip_path, with_hub)      # so the other laptop finds it through OneDrive
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        say(f"The update didn't finish: {exc}")
        say("Nothing is broken. Close Jarvis Hub, run this again, and if it still fails tell Claude what it says.")
        return 1
    if not is_core:
        say("")
        say("This laptop is up to date. Jarvis core runs on Laptop B, so now run this same file there")
        say("(it's in OneDrive > Documents > JarvisHub) to finish" + (" and switch review recording on." if review else "."))
        return 0
    if review:
        root = Path(env.get("JARVIS_ROOT") or r"C:\Jarvis")
        until = review_on(root)
        say("")
        say(f"Review recording is ON until {time.strftime('%A %d %B, %I:%M %p', time.localtime(until))}.")
        say(f"Everything about each conversation is kept in {root / 'logs' / 'review'}, on this laptop only.")
        say('To stop early: "Stop review recording.bat".')
    say("")
    say("Restarting Jarvis core...")
    (restart or restart_core)(code)
    say("")
    say("Checking that everything works on this laptop (a few seconds)...")
    (report or write_report)(code)
    say("")
    say("Done. Close Jarvis Hub and open it again (on both laptops) so it runs the new version.")
    return 0


def write_report(code):
    """tools/doctor.py: one page on what works here, saved where Claude can read it (OneDrive). Never fails the update."""
    doctor = Path(code) / "tools" / "doctor.py"
    if not doctor.is_file():
        return
    time.sleep(8)   # the core needs a moment after a restart
    try:
        out = subprocess.run([sys.executable, str(doctor)], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60, cwd=str(code))
        last = [x for x in out.stdout.splitlines() if x.startswith("Saved to ")]
        print(last[-1] if last else "The check ran but could not save its report.")
    except (OSError, subprocess.SubprocessError):
        print("The check could not run. The update itself is done.")


def restart_core(code):
    bat = Path(code) / "restart-core.bat"
    if bat.is_file():
        subprocess.call(["cmd", "/c", str(bat)], stdin=subprocess.DEVNULL, cwd=str(code))


if __name__ == "__main__":
    sys.exit(main(sys.argv[0]))
