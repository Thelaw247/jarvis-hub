"""Web windows on the desktop (R1, REACH §5.1): let the hub's own pages show sites that refuse to be framed, and
keep signed-in pages in a browser profile that belongs to the hub.

Framing. Many sites (Google, GitHub, Canvas) send `X-Frame-Options` or a CSP `frame-ancestors` rule, so a browser
won't show them inside another page. WebView2 lets the app that hosts it add allowed ancestors per frame
navigation: `CoreWebView2NavigationStartingEventArgs.AdditionalAllowedFrameAncestors`
(https://learn.microsoft.com/microsoft-edge/webview2/concepts/frames). We set it only when all of these hold:
  - the navigation is in a frame that is a direct child of the top page (CoreWebView2.FrameCreated gives us
    exactly those; nested frames inside a framed site are left alone),
  - the top page is the hub itself (its origin is one of the hub's), and
  - the frame is going to an http(s) address.
The value is the hub's own origin(s) only, never a wildcard, as Microsoft's remarks advise (clickjacking: only
origins we fully trust may embed).

The bridge stays out of frames. pywebview injects `window.pywebview` with ExecuteScriptAsync into the top
document only and listens on CoreWebView2.WebMessageReceived, which only hears the top document. This module never
calls AddHostObjectToScript, never posts to or listens on a frame's web messages, and never adds a script to
frames. In the page, every frame also gets a sandbox without top navigation (ui/components/web-frame).

Signed-in pages. The desktop app keeps its browser data in a profile folder of its own,
%LOCALAPPDATA%\\JarvisHub\\webprofile: he signs in there once (inside a web window) and stays signed in, separate
from his everyday Chrome or Edge. Nothing about his accounts is in this code; to sign out of everything, close
the hub and delete that folder.

Everything here is a no-op off Windows, without pywebview's WebView2 backend, or on a runtime without the
frame API; a web window then shows its card for sites that refuse framing.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

PROFILE_PARTS = ("JarvisHub", "webprofile")


def profile_dir(environ: dict | None = None, platform: str | None = None) -> Path | None:
    """%LOCALAPPDATA%\\JarvisHub\\webprofile on Windows; None elsewhere or when LOCALAPPDATA isn't set."""
    environ = os.environ if environ is None else environ
    platform = sys.platform if platform is None else platform
    base = environ.get("LOCALAPPDATA")
    if not platform.startswith("win") or not base:
        return None
    return Path(base).joinpath(*PROFILE_PARTS)


def start_options(environ: dict | None = None, platform: str | None = None) -> dict:
    """Extra keyword arguments for webview.start(): a lasting profile in the hub's own folder (not private mode,
    which forgets every sign-in when the app closes). Empty when there is no such folder (not Windows)."""
    folder = profile_dir(environ, platform)
    return {"private_mode": False, "storage_path": str(folder)} if folder else {}


def origin_of(url: str | None) -> str | None:
    """scheme://host[:port] for an http(s) address, lower-case; None for anything else."""
    try:
        parts = urlsplit(str(url or "").strip())
    except ValueError:
        return None
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        return None
    try:
        port = parts.port
    except ValueError:
        return None
    default = {"http": 80, "https": 443}[parts.scheme.lower()]
    host = parts.hostname.lower()
    if ":" in host:  # IPv6
        host = f"[{host}]"
    return f"{parts.scheme.lower()}://{host}" + (f":{port}" if port and port != default else "")


def hub_origins(*urls: str | None) -> tuple[str, ...]:
    """The hub's origins from its addresses (the local server, a --hub address), without repeats.
    127.0.0.1 and localhost are both added for a local hub, since either may be typed."""
    out: list[str] = []
    for url in urls:
        origin = origin_of(url)
        if not origin:
            continue
        twins = [origin]
        if "://127.0.0.1" in origin:
            twins.append(origin.replace("://127.0.0.1", "://localhost"))
        elif "://localhost" in origin:
            twins.append(origin.replace("://localhost", "://127.0.0.1"))
        out.extend(o for o in twins if o not in out)
    return tuple(out)


def allowed_ancestors(frame_url: str | None, top_url: str | None, origins: tuple[str, ...]) -> str | None:
    """The AdditionalAllowedFrameAncestors value for one frame navigation, or None to leave it alone: only an
    http(s) frame in a top page that is the hub, and only the hub's own origins (space-separated, CSP style)."""
    if not origins or origin_of(top_url) not in origins or not origin_of(frame_url):
        return None
    return " ".join(origins)


class FrameGuard:
    """Hooks one CoreWebView2: every first-level frame's NavigationStarting gets the hub as an allowed ancestor.
    Works on the real .NET objects (through pythonnet) and on plain fakes in the tests."""

    def __init__(self, origins: tuple[str, ...], log=print) -> None:
        self.origins = tuple(origins)
        self.core = None
        self.log = log
        self.frames = 0  # frames seen (for the tests and the log)
        self.allowed = 0  # navigations given the hub as an ancestor

    def attach(self, core) -> bool:
        """Subscribe to the frame events of `core` (a CoreWebView2). → False when the runtime has no frame API."""
        if core is None or not self.origins:
            return False
        self.core = core
        try:
            if hasattr(core, "FrameCreated"):  # recommended: CoreWebView2Frame.NavigationStarting (SDK 1.0.2210+)
                core.FrameCreated += self.on_frame_created
                return True
            if hasattr(core, "FrameNavigationStarting"):  # older runtimes: the superseded CoreWebView2 event
                core.FrameNavigationStarting += self.on_navigation_starting
                return True
        except Exception as err:  # noqa: BLE001 - a nicety, never a reason for the hub to fail
            self.log(f"Web windows: couldn't watch frames ({err}).")
        return False

    def on_frame_created(self, _sender, args) -> None:
        try:
            frame = args.Frame
            self.frames += 1
            frame.NavigationStarting += self.on_navigation_starting
        except Exception as err:  # noqa: BLE001
            self.log(f"Web windows: a frame couldn't be watched ({err}).")

    def on_navigation_starting(self, _sender, args) -> None:
        try:
            top = getattr(self.core, "Source", None)
            value = allowed_ancestors(str(args.Uri), str(top) if top is not None else None, self.origins)
            if value:
                args.AdditionalAllowedFrameAncestors = value
                self.allowed += 1
        except Exception as err:  # noqa: BLE001
            self.log(f"Web windows: a frame's ancestors couldn't be set ({err}).")


def _control(window):
    """The WebView2 WinForms control behind a pywebview window (window.native is the form), or None."""
    native = getattr(window, "native", None)
    return getattr(native, "webview", None) or getattr(getattr(native, "browser", None), "webview", None)


def install(window, origins: tuple[str, ...], platform: str | None = None, log=print) -> FrameGuard | None:
    """Watch the frames of one pywebview window once its WebView2 is ready. Call before webview.start().
    → the guard, or None when this can't apply (not Windows, no origins, an old pywebview)."""
    platform = sys.platform if platform is None else platform
    events = getattr(window, "events", None)
    if not platform.startswith("win") or not origins or events is None or not hasattr(events, "before_show"):
        return None
    guard = FrameGuard(origins, log=log)

    def ready(sender, args) -> None:  # CoreWebView2InitializationCompleted, on the UI thread
        if getattr(args, "IsSuccess", True):
            guard.attach(getattr(sender, "CoreWebView2", None))

    def before_show(window) -> None:  # pywebview runs this on the UI thread, right after making the control
        control = _control(window)
        if control is None:
            return  # not the WebView2 backend (CEF, MSHTML): nothing to do
        try:
            core = getattr(control, "CoreWebView2", None)
            if core is not None:
                guard.attach(core)
            else:
                control.CoreWebView2InitializationCompleted += ready
        except Exception as err:  # noqa: BLE001
            log(f"Web windows: WebView2 isn't reachable ({err}).")

    try:
        events.before_show += before_show
    except Exception as err:  # noqa: BLE001
        log(f"Web windows: couldn't hook the window ({err}).")
        return None
    return guard


def start(webview, windows, urls, **kwargs) -> list[FrameGuard]:
    """The one call app.py makes instead of webview.start(): hook every window (the hub and the Stage), then
    start the GUI with the hub's own browser profile. `urls`: the hub's addresses (its origin may frame pages).
    → the guards that were installed (for the log)."""
    origins = hub_origins(*urls)
    guards = [g for g in (install(w, origins) for w in windows if w is not None) if g]
    options = {**start_options(), **kwargs}
    folder = options.get("storage_path")
    if folder:
        try:
            Path(folder).mkdir(parents=True, exist_ok=True)
        except OSError as err:
            print(f"Web windows: the profile folder couldn't be made ({err}); using a private session.", flush=True)
            options.pop("storage_path", None)
            options.pop("private_mode", None)
    webview.start(**options)
    return guards
