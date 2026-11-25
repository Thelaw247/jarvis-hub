"""Web windows on the desktop (R1, jarvis_hub/webframes.py), with fakes for pywebview and WebView2: the hub's
pages may frame sites that refuse it, nothing else may, the bridge is never handed to a frame, and signed-in
pages live in the hub's own profile folder."""
from pathlib import Path

from jarvis_hub import webframes as wf

HUB = "http://127.0.0.1:8781/"
ORIGINS = wf.hub_origins(HUB)


class Event:
    """A .NET-style event: `+=` adds a handler (pythonnet does the same with Python callables)."""

    def __init__(self):
        self.handlers = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self

    def fire(self, *args):
        for h in self.handlers:
            h(*args)


class Args:
    def __init__(self, uri):
        self.Uri = uri
        self.AdditionalAllowedFrameAncestors = ""


class Frame:
    def __init__(self):
        self.NavigationStarting = Event()


class Core:
    """CoreWebView2 with the frame API (FrameCreated → CoreWebView2Frame.NavigationStarting)."""

    def __init__(self, source=HUB + "?window=stage#/stage"):
        self.Source = source
        self.FrameCreated = Event()

    def make_frame(self):
        frame = Frame()
        self.FrameCreated.fire(self, type("FrameArgs", (), {"Frame": frame})())
        return frame


class OldCore:
    """An older runtime: only the superseded CoreWebView2.FrameNavigationStarting."""

    def __init__(self, source=HUB):
        self.Source = source
        self.FrameNavigationStarting = Event()


def navigate(frame, url):
    args = Args(url)
    frame.NavigationStarting.fire(frame, args)
    return args.AdditionalAllowedFrameAncestors


def test_origins_are_the_hubs_own_and_local_twins():
    assert wf.origin_of("https://Docs.Google.com/document/d/x/edit?a=1") == "https://docs.google.com"
    assert wf.origin_of("http://127.0.0.1:80/x") == "http://127.0.0.1"
    assert wf.origin_of("javascript:alert(1)") is None and wf.origin_of("file:///C:/x.html") is None and wf.origin_of("") is None
    assert ORIGINS == ("http://127.0.0.1:8781", "http://localhost:8781")
    assert wf.hub_origins("https://hub.tailnet.ts.net/", None, "https://hub.tailnet.ts.net/#/now") == ("https://hub.tailnet.ts.net",)


def test_ancestors_only_for_http_frames_inside_the_hub():
    google = "https://www.google.com/search?q=method+of+joints"
    assert wf.allowed_ancestors(google, HUB, ORIGINS) == "http://127.0.0.1:8781 http://localhost:8781"
    assert wf.allowed_ancestors(google, "https://evil.example/", ORIGINS) is None  # the top page isn't the hub
    assert wf.allowed_ancestors("javascript:alert(1)", HUB, ORIGINS) is None
    assert wf.allowed_ancestors("data:text/html,hi", HUB, ORIGINS) is None
    assert wf.allowed_ancestors(google, None, ORIGINS) is None
    assert wf.allowed_ancestors(google, HUB, ()) is None
    assert "*" not in wf.allowed_ancestors(google, HUB, ORIGINS)  # never a wildcard (clickjacking)


def test_first_level_frames_of_the_hub_get_the_hub_as_ancestor():
    core = Core()
    guard = wf.FrameGuard(ORIGINS)
    assert guard.attach(core)
    frame = core.make_frame()
    assert navigate(frame, "https://github.com/") == "http://127.0.0.1:8781 http://localhost:8781"
    assert navigate(frame, "about:blank") == ""
    assert guard.frames == 1 and guard.allowed == 1


def test_a_frame_in_a_page_that_is_not_the_hub_is_left_alone():
    core = Core(source="https://www.example.com/")  # the top page navigated away from the hub somehow
    guard = wf.FrameGuard(ORIGINS)
    guard.attach(core)
    assert navigate(core.make_frame(), "https://www.google.com/") == ""


def test_older_runtimes_use_the_superseded_event():
    core = OldCore()
    assert wf.FrameGuard(ORIGINS).attach(core)
    args = Args("https://docs.google.com/document/d/x/edit")
    core.FrameNavigationStarting.fire(core, args)
    assert args.AdditionalAllowedFrameAncestors.startswith("http://127.0.0.1:8781")


def test_no_frame_api_or_no_core_is_a_no_op():
    assert not wf.FrameGuard(ORIGINS).attach(None)
    assert not wf.FrameGuard(ORIGINS).attach(type("Bare", (), {"Source": HUB})())
    assert not wf.FrameGuard(()).attach(Core())


def test_a_failing_handler_never_breaks_the_hub():
    logs = []
    guard = wf.FrameGuard(ORIGINS, log=logs.append)
    guard.attach(Core())

    class Broken:
        @property
        def Uri(self):
            raise RuntimeError("COM went away")

    guard.on_navigation_starting(None, Broken())
    guard.on_frame_created(None, object())
    assert len(logs) == 2


class Control:
    """The WebView2 WinForms control before its CoreWebView2 is ready."""

    def __init__(self):
        self.CoreWebView2 = None
        self.CoreWebView2InitializationCompleted = Event()


class Window:
    def __init__(self, control):
        self.native = type("Form", (), {"webview": control})()
        self.events = type("Events", (), {"before_show": Event()})()


def test_install_waits_for_webview2_then_watches_frames():
    control = Control()
    window = Window(control)
    guard = wf.install(window, ORIGINS, platform="win32")
    assert guard is not None
    window.events.before_show.fire(window)  # pywebview: on the UI thread, right after making the control
    core = Core()
    control.CoreWebView2 = core
    control.CoreWebView2InitializationCompleted.fire(control, type("Done", (), {"IsSuccess": True})())
    assert navigate(core.make_frame(), "https://www.google.com/").startswith("http://127.0.0.1:8781")


def test_install_attaches_at_once_when_webview2_is_already_ready():
    control = Control()
    control.CoreWebView2 = Core()
    window = Window(control)
    guard = wf.install(window, ORIGINS, platform="win32")
    window.events.before_show.fire(window)
    assert guard.core is control.CoreWebView2


def test_install_is_a_no_op_off_windows_or_without_pywebview_events():
    assert wf.install(Window(Control()), ORIGINS, platform="linux") is None
    assert wf.install(object(), ORIGINS, platform="win32") is None
    assert wf.install(Window(Control()), (), platform="win32") is None
    window = Window(None)  # not the WebView2 backend (CEF, MSHTML)
    wf.install(window, ORIGINS, platform="win32")
    window.events.before_show.fire(window)  # nothing to do, nothing raised


def test_the_profile_is_the_hubs_own_folder_and_only_on_windows():
    env = {"LOCALAPPDATA": r"C:\Users\someone\AppData\Local"}
    folder = wf.profile_dir(env, "win32")
    assert folder == Path(r"C:\Users\someone\AppData\Local") / "JarvisHub" / "webprofile"
    assert wf.start_options(env, "win32") == {"private_mode": False, "storage_path": str(folder)}
    assert wf.profile_dir(env, "linux") is None and wf.start_options(env, "linux") == {}
    assert wf.profile_dir({}, "win32") is None


def test_start_installs_on_every_window_and_starts_once(monkeypatch, tmp_path):
    monkeypatch.setattr(wf, "start_options", lambda: {"private_mode": False, "storage_path": str(tmp_path / "webprofile")})
    seen = []
    monkeypatch.setattr(wf, "install", lambda w, origins: seen.append((w, origins)) or object())
    started = []
    fake = type("Webview", (), {"start": staticmethod(lambda **kw: started.append(kw))})
    guards = wf.start(fake, ["hub", None, "stage"], [HUB + "?window=stage#/stage"])
    assert [w for w, _ in seen] == ["hub", "stage"] and all(o == ORIGINS for _, o in seen) and len(guards) == 2
    assert started == [{"private_mode": False, "storage_path": str(tmp_path / "webprofile")}]
    assert (tmp_path / "webprofile").is_dir()


def test_the_bridge_is_never_handed_to_a_frame():
    source = Path(wf.__file__).read_text(encoding="utf-8")
    code = source.split('"""', 2)[2]  # past the module docstring, which names these to say we don't use them
    for call in ("AddHostObjectToScript", "PostWebMessage", "AddScriptToExecuteOnDocumentCreated", "WebMessageReceived", "ExecuteScript"):
        assert call not in code
