"""Jarvis Hub. Run with:  python app.py

Options:
  --demo          use the built-in demo day instead of jarvis-core (made-up data, for trying the hub); it follows the real clock
  --fixture-clock keep the demo day on its own date (Monday 2026-11-16, 3:40 pm), as the screenshots and tests do
  --hub URL       show a live hub instead (e.g. https://hub.tailnet.ts.net); the same UI, served by that hub
  --ambient       open full screen as the ambient screen (Laptop B)
  --strip         open the small always-on-top strip (Laptop A); nothing in it animates
  --browser       open in an Edge app window instead of the native window
  --no-window     start the server and print its address (used by the tests)
  --port N        port for the local server (default: a free one)
  --device A|B    which laptop this is (default: A with --strip, else B); Laptop A hides an empty Stage
  --stage-screen N  the monitor the Stage fills (0, 1, ...; default: the primary one); env JARVIS_STAGE_SCREEN
  --no-stage      don't make the Stage window (windows then only show on the hub with "On the hub")

One window (v0.17.0, the default: Controls > Screens > "Where Jarvis shows things" = On the hub): what Jarvis
pulls up shows on the hub itself. A second, ordinary window (the holder, "Jarvis Windows") is made hidden at
start and comes up only while he has pulled a window out of the hub; it has no orb and no voice, and closing it
sends its windows back.

The Stage (HUD v2 §6.5, the other setting; read once at start): the windows Jarvis pulls up show in a second,
borderless window, full screen on the chosen monitor, so the hub's home page stays calm. It is made hidden at
start (it then appears within ~100 ms instead of a 0.5-1 s cold start), shown when the first window is pushed,
never in game mode, and when the last window is put away it stays on standby (Laptop B) or hides (Laptop A).
should_show_stage() decides.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path

# Started from the Start menu there is no terminal, so Python has nowhere to print.
# Send messages and errors to jarvishub.log instead of failing silently (same as Pen Reader).
if sys.stdout is None or sys.stderr is None:
    try:
        if getattr(sys, "frozen", False):  # installed app: its own folder may not be writable
            _dir = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "JarvisHub"
            _dir.mkdir(parents=True, exist_ok=True)
        else:
            _dir = Path(__file__).resolve().parent
        _log = open(_dir / "jarvishub.log", "w", buffering=1, encoding="utf-8")
    except OSError:
        _log = open(os.devnull, "w")
    sys.stdout = sys.stderr = _log
    try:  # if the app is ever killed by a crash below Python, say where
        import faulthandler

        faulthandler.enable(file=_log)
    except Exception:  # noqa: BLE001
        pass
    print(f"Jarvis Hub starting (Python {sys.version.split()[0]})", flush=True)

from jarvis_hub import settings as S

TITLE = S.APP_NAME
STAGE_TITLE = f"{TITLE} Stage"
HOLDER_TITLE = "Jarvis Windows"   # one window (v0.17.0): the second window only holds what he pulls out of the hub
HOLDER_SIZE = (960, 640)
SIZES = {"full": (1280, 800), "strip": (360, 96)}
CANVAS = {"day": "#f3ecdf", "night": "#0e141c"}  # window background before the page paints (tokens: --canvas)
# Jarvis's earcons (wake, tick, critical) must play without a click first: voice wakes him, not the mouse.
AUTOPLAY = "--autoplay-policy=no-user-gesture-required"


def allow_autoplay() -> None:
    """WebView2 reads extra browser switches from this variable (pywebview has no option for them)."""
    have = os.environ.get("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "")
    if AUTOPLAY not in have:
        os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"{have} {AUTOPLAY}".strip()


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class LocalHub:
    """The hub server (FastAPI + demo backend) on 127.0.0.1, in a background thread."""

    def __init__(self, port: int = 0) -> None:
        import uvicorn

        from jarvis_hub.server import create_app

        self.port = port or free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        config = uvicorn.Config(create_app(), host="127.0.0.1", port=self.port, log_level="warning", access_log=False)
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, name="jarvis-hub", daemon=True)

    def start(self) -> None:
        self.thread.start()
        for _ in range(200):
            if self.server.started:
                return
            time.sleep(0.025)
        raise RuntimeError("The hub server did not start.")

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=3)

    def wait_until_closed(self, grace: float = 6.0) -> None:
        """Return once a window has connected and then been gone for a few seconds."""
        hub = self.server.config.app.state.hub
        had_client, gone_since = False, 0.0
        try:
            while True:
                time.sleep(1.0)
                if hub.clients:
                    had_client, gone_since = True, 0.0
                elif had_client:
                    gone_since += 1.0
                    if gone_since > grace:
                        return
        except KeyboardInterrupt:
            return


def page_url(base: str, mode: str) -> str:
    query = {"full": "", "ambient": "?size=ambient", "strip": "?size=strip", "stage": "?window=stage#/stage"}[mode]
    return f"{base.rstrip('/')}/{query}"


# ---- the Stage: a second window for the windows Jarvis pulls up (HUD v2 §6.5) ----------------------------

def in_game(state: dict | None, settings: dict | None) -> bool:
    """Game mode is on: set to On, or Auto with a game running (the hub's moment says "game")."""
    settings, state = settings or {}, state or {}
    return settings.get("game_mode") == "on" or (state.get("now_card") or {}).get("moment") == "game"


def should_show_stage(state: dict | None, settings: dict | None, device: str, showing: bool = False) -> bool:
    """Whether the Stage window should be on screen. `state` needs `windows` and `now_card.moment`, `settings`
    needs `stage` and `game_mode` (ui/views/stage/desktop.js stageReport sends exactly these), `device` is
    "A" or "B", `showing` whether it is up now.
    - Game mode: never (it would cover the game; the recap waits on the Rail).
    - "On the hub" (one window: settings.stage = "hub", the default since v0.17.0 and when unset): the second
      window is only a holder for windows he pulled out of the hub, so it is up exactly while some are
      (`state.popped`, a count).
    - Stage window (settings.stage = "window"): up while a window is up; with nothing up, Laptop B keeps it on
      standby (the orb and the clock) if it was up and Laptop A hides it."""
    settings, state = settings or {}, state or {}
    if in_game(state, settings):
        return False
    if settings.get("stage", "hub") != "window":
        return int(state.get("popped") or 0) > 0
    if state.get("windows"):
        return True
    return bool(showing) and str(device).upper() != "A"


def stage_screen(screens: list, index: int | None = None):
    """The monitor the Stage fills: screens[index] if there is one, else the primary (the one at 0, 0), else
    the first. → the screen, or None when pywebview gave no screens."""
    screens = list(screens or [])
    if not screens:
        return None
    if index is not None and 0 <= index < len(screens):
        return screens[index]
    return next((s for s in screens if getattr(s, "x", 0) == 0 and getattr(s, "y", 0) == 0), screens[0])


class StageApi:
    """The JS API both windows get (window.pywebview.api). Methods only: pywebview exposes every public
    attribute, so the windows live on a private holder. Every call is defensive: the Stage is a nicety, never a
    reason for the hub to fail."""

    def __init__(self, device: str = "B") -> None:
        self._w = type("Windows", (), {"hub": None, "stage": None})()
        self._device = device
        self._showing = False
        self._last: dict = {}  # the hub window's last report
        self._lock = threading.Lock()

    def _attach(self, hub, stage) -> None:
        self._w.hub, self._w.stage = hub, stage

    def _set(self, show: bool, front: bool = False) -> bool:
        stage = self._w.stage
        if stage is None:
            return False
        with self._lock:
            try:
                if show and (front or not self._showing):
                    stage.show()
                    if front:
                        _bring_to_front(stage)
                elif not show and self._showing:
                    stage.hide()
                self._showing = show
                return True
            except Exception as err:  # noqa: BLE001
                print(f"The Stage window didn't {'show' if show else 'hide'} ({err}).", flush=True)
                return False

    def sync_stage(self, report: dict | None = None) -> bool:
        """The hub window reports what decides the Stage whenever it changes. → whether the Stage is up."""
        report = report if isinstance(report, dict) else {}
        self._last = report
        want = should_show_stage(report.get("state"), report.get("settings"), self._device, self._showing)
        if want != self._showing:
            # a window he just pulled out of the hub should be seen: the holder comes to the front
            self._set(want, front=want and (report.get("settings") or {}).get("stage", "hub") != "window")
        return self._showing

    def show_stage(self) -> bool:
        """The "Stage · N" chip: bring the Stage to the front (it still never covers a game, and with "On the
        hub" there is no Stage to show)."""
        settings, state = self._last.get("settings") or {}, self._last.get("state") or {}
        if in_game(state, settings):
            return False
        if settings.get("stage", "hub") != "window" and not int(state.get("popped") or 0):
            return False  # one window, nothing pulled out: there is no second window to show
        return self._set(True, front=True)

    def _holder_closed(self) -> bool:
        """He closed the holder: everything he had pulled out goes back to the hub."""
        hub = self._w.hub
        if hub is None:
            return False
        try:
            (getattr(hub, "run_js", None) or hub.evaluate_js)("window.__jarvis && window.__jarvis.popped && window.__jarvis.popped.clear()")
            return True
        except Exception as err:  # noqa: BLE001
            print(f"Couldn't move the windows back to the hub ({err}).", flush=True)
            return False

    def hide_stage(self) -> bool:
        return self._set(False)

    def focus_hub(self, path: str | None = None) -> bool:
        """The Stage's Hub pill, or a link inside a Stage window: the hub comes to the front, at `path`."""
        hub = self._w.hub
        if hub is None:
            return False
        try:
            if path and isinstance(path, str) and path.startswith("/"):
                js = f"window.__jarvis && window.__jarvis.router.go({json.dumps(path)})"
                (getattr(hub, "run_js", None) or hub.evaluate_js)(js)
            hub.restore()
            hub.show()
            _bring_to_front(hub)
            return True
        except Exception as err:  # noqa: BLE001
            print(f"Couldn't bring the hub to the front ({err}).", flush=True)
            return False


def _bring_to_front(window) -> None:
    """Raise a window above the others without keeping it on top (pywebview has no focus call)."""
    try:
        window.on_top = True
        window.on_top = False
    except Exception:  # noqa: BLE001
        pass


def saved_stage(base: str, timeout: float = 2.0) -> str:
    """Where Jarvis shows things, as saved: "window" (the Stage) or "hub" (one window; also when unset or when
    the hub can't say in time). Read once at start, because the second window is made differently for each."""
    try:
        from urllib.request import urlopen

        with urlopen(f"{base.rstrip('/')}/api/state", timeout=timeout) as reply:  # noqa: S310 - our own hub server
            settings = (json.loads(reply.read().decode("utf-8")) or {}).get("settings") or {}
        return "window" if settings.get("stage") == "window" else "hub"
    except Exception:  # noqa: BLE001 - the hub or jarvis-core isn't answering yet: one window
        return "hub"


def create_stage(webview, base: str, api: StageApi, screen_index: int | None, holder: bool = False):
    """Make the second window, hidden. The Stage (`holder` False): borderless, covering the chosen monitor.
    The holder (one window, v0.17.0): an ordinary window he can move and size, for the windows he pulls out of
    the hub. → the window or None."""
    try:
        screen = stage_screen(getattr(webview, "screens", []), screen_index)
    except Exception:  # noqa: BLE001 - no screens API: the default monitor
        screen = None
    geometry = {}
    if holder:
        geometry = {"width": HOLDER_SIZE[0], "height": HOLDER_SIZE[1], "min_size": (360, 240)}
    elif screen is not None:
        geometry = {"x": getattr(screen, "x", 0), "y": getattr(screen, "y", 0), "width": screen.width, "height": screen.height}
    options = dict(title=HOLDER_TITLE if holder else STAGE_TITLE, url=page_url(base, "stage"), js_api=api, hidden=True,
                   frameless=not holder, easy_drag=False, background_color=CANVAS["night"], text_select=True, **geometry)
    if holder:
        screen = None  # wherever Windows puts it; he moves it where he wants it
    for extra in ({"screen": screen} if screen is not None else {}, {}):
        try:
            return webview.create_window(**options, **extra)
        except TypeError:  # an older pywebview without screen= (or hidden=): try the plain form
            continue
        except Exception as err:  # noqa: BLE001
            print(f"The Stage window couldn't be made ({err}). Windows will show on the hub.", flush=True)
            return None
    return None


def _windows_identity() -> None:
    """Give the app its own taskbar button, so Windows shows our icon rather than Python's."""
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(S.APP_ID)
    except Exception:  # noqa: BLE001 - not Windows, or not allowed
        pass


def _set_window_icon(title: str = TITLE) -> None:
    """Put the Jarvis icon on the native window and its taskbar button."""
    try:
        import ctypes

        user32 = ctypes.windll.user32
        user32.FindWindowW.restype = ctypes.c_void_p
        user32.LoadImageW.restype = ctypes.c_void_p
        user32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
        hwnd = user32.FindWindowW(None, title)
        if not hwnd:
            return
        icon = str(S.resource_path("ui", "icons", "app.ico"))
        for which, size in ((0, 16), (1, 32)):  # ICON_SMALL, ICON_BIG
            handle = user32.LoadImageW(None, icon, 1, size, size, 0x10)  # IMAGE_ICON, LR_LOADFROMFILE
            if handle:
                user32.SendMessageW(hwnd, 0x80, which, handle)  # WM_SETICON
    except Exception:  # noqa: BLE001 - the icon is a nicety, never a reason to fail
        pass


def run_native(url: str, mode: str, stage: dict | None = None) -> bool:
    """Open the native window (WebView2), and the hidden Stage beside it unless `stage` is None
    (`{"base": hub address, "device": "A"|"B", "screen": index or None}`). Returns False if it could not start."""
    try:
        import webview
    except Exception as err:  # noqa: BLE001
        print(f"Native window not available ({err}). Opening in a browser window instead.")
        return False
    try:
        allow_autoplay()
        width, height = SIZES["strip" if mode == "strip" else "full"]
        api = StageApi(stage["device"] if stage else "B")
        window = webview.create_window(
            TITLE, url=url, width=width, height=height, js_api=api,
            min_size=(320, 90), background_color=CANVAS["night"], text_select=True,
            fullscreen=(mode == "ambient"), on_top=(mode == "strip"), frameless=False,
        )
        window.events.shown += lambda *a: _set_window_icon()
        holder = bool(stage) and saved_stage(stage["base"]) != "window"  # one window: the second only holds what he pulls out
        stage_window = create_stage(webview, stage["base"], api, stage.get("screen"), holder=holder) if stage else None
        api._attach(window, stage_window)
        if stage_window is not None and holder:
            stage_window.events.shown += lambda *a: _set_window_icon(HOLDER_TITLE)
        if stage_window is not None:
            quitting = threading.Event()

            def hub_closed(*_a):  # the hub is the app: closing it closes the Stage too
                quitting.set()
                try:
                    stage_window.destroy()
                except Exception:  # noqa: BLE001
                    pass

            def stage_closing(*_a):  # Alt+F4 on the Stage hides it; it comes back with the next window
                if quitting.is_set():
                    return True
                if holder:  # closing the holder sends its windows back to the hub (which then hides it)
                    api._holder_closed()
                api.hide_stage()
                return False

            window.events.closed += hub_closed
            stage_window.events.closing += stage_closing
        from jarvis_hub import webframes  # web windows: frame refusing sites, the hub's own profile (R1)

        webframes.start(webview, [window, stage_window], [url])
        return True
    except Exception as err:  # noqa: BLE001
        print(f"Native window failed to start ({err}). Opening in a browser window instead.")
        return False


def open_app_window(url: str, mode: str = "full") -> None:
    """Open the page in a chromeless Edge (or Chrome) window, else the default browser."""
    width, height = SIZES["strip" if mode == "strip" else "full"]
    candidates = [
        shutil.which("msedge"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        shutil.which("chrome"),
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
    ]
    extra = ["--start-fullscreen"] if mode == "ambient" else [f"--window-size={width},{height}"]
    for exe in candidates:
        if exe and os.path.isfile(exe):
            try:
                subprocess.Popen([exe, f"--app={url}", AUTOPLAY, *extra])
                return
            except OSError:
                continue
    webbrowser.open(url)


def _env_int(name: str) -> int | None:
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Jarvis Hub")
    parser.add_argument("--demo", action="store_true", help="use the built-in demo day instead of jarvis-core")
    parser.add_argument("--fixture-clock", action="store_true", help="keep the demo day on its own date instead of now")
    parser.add_argument("--hub", metavar="URL", help="show a live hub at this address instead of the demo")
    parser.add_argument("--ambient", action="store_true", help="full-screen ambient screen")
    parser.add_argument("--strip", action="store_true", help="small always-on-top strip")
    parser.add_argument("--browser", action="store_true", help="use an Edge app window")
    parser.add_argument("--no-window", action="store_true", help="start the server only")
    parser.add_argument("--port", type=int, default=int(os.environ.get("JARVIS_HUB_PORT", "0")))
    parser.add_argument("--device", choices=["A", "B", "a", "b"], default=os.environ.get("JARVIS_DEVICE") or None,
                        help="which laptop this is: A (games, the strip) or B (default: A with --strip, else B)")
    parser.add_argument("--stage-screen", type=int, metavar="N", default=_env_int("JARVIS_STAGE_SCREEN"),
                        help="the monitor the Stage fills (0, 1, ...; default: the primary one)")
    parser.add_argument("--no-stage", action="store_true", help="don't make the Stage window")
    args = parser.parse_args(argv)
    if args.hub and args.demo:
        parser.error("Choose --demo or --hub URL, not both.")
    if args.hub and not args.hub.startswith(("http://", "https://")):
        parser.error("--hub needs a full address, for example https://hub.example.ts.net")
    mode = "strip" if args.strip else "ambient" if args.ambient else "full"
    device = (args.device or ("A" if mode == "strip" else "B")).upper()

    _windows_identity()
    local = voice = None
    if args.hub:
        base = args.hub
    else:
        # live by default (H5): the hub shows jarvis-core (JARVIS_CORE_URL + JARVIS_CORE_SESSION), or an honest
        # "not set up" screen. The demo day only with --demo; it moves to the real clock (HUD v2 §11).
        if args.demo or args.fixture_clock:
            os.environ["JARVIS_HUB_MODE"] = "demo"
        if args.fixture_clock:
            os.environ["JARVIS_DEMO_CLOCK"] = "fixture"
        else:
            os.environ.setdefault("JARVIS_DEMO_CLOCK", "real")
        local = LocalHub(args.port)
        local.start()
        base = local.url
        if os.environ.get("JARVIS_HUB_MODE") != "demo" and not args.no_window:
            # one icon (v0.15.0): the hub runs this laptop's voice itself, hidden (jarvis_hub/voicehost.py)
            from jarvis_hub.voicehost import VoiceHost

            voice = VoiceHost(Path(__file__).resolve().parent)
            local.server.config.app.state.voicehost = voice
            threading.Thread(target=voice.start, name="jarvis-voice-start", daemon=True).start()
    url = page_url(base, mode)
    print(f"Jarvis Hub is running at {url}", flush=True)

    try:
        if args.no_window:
            while True:
                time.sleep(3600)
        elif args.browser or not run_native(url, mode, None if args.no_stage else {"base": base, "device": device, "screen": args.stage_screen}):
            open_app_window(url, mode)
            if local:
                local.wait_until_closed()
    except KeyboardInterrupt:
        pass
    finally:
        if voice:
            voice.stop()
        if local:
            local.stop()
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except SystemExit as stop:
        code = stop.code
    except Exception:  # noqa: BLE001 - leave a trace in the log, then stop
        traceback.print_exc()
        code = 1
    sys.exit(code)
