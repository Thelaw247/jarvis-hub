"""His open windows on this laptop: which are open, and putting them side by side on one screen.

His ask of 2026-11-22: with the hub on the monitor, Jarvis should lay out the laptop screen for the work at hand (the
Canvas page on one half, Claude on the other), and ask first so he can stop typing before anything moves.

`tile` and `match` are plain arithmetic and text (tested anywhere). `Desktop` talks to Windows itself through ctypes:
no extra package, a few milliseconds. It only moves and sizes windows; it never closes one, types into one or reads
what is inside one. Window titles are read only when he asks for an arrangement, and are not kept.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass

HUB_TITLE = "Jarvis Hub"
SKIP_TITLES = ("Program Manager", "Windows Input Experience", "Settings", "Jarvis Windows")


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int


@dataclass(frozen=True)
class Win:
    handle: int
    title: str
    screen: int          # index into Desktop.screens()
    minimized: bool = False


def tile(n: int, area: Rect) -> list[Rect]:
    """Where n windows go on one screen, left to right in the order he named them: one fills it, two share it side
    by side, three are one tall on the left and two stacked on the right, four are quarters."""
    n = max(1, min(n, 4))
    half_w, half_h = area.w // 2, area.h // 2
    left = Rect(area.x, area.y, half_w, area.h)
    right = Rect(area.x + half_w, area.y, area.w - half_w, area.h)
    if n == 1:
        return [area]
    if n == 2:
        return [left, right]
    top_r = Rect(right.x, area.y, right.w, half_h)
    bot_r = Rect(right.x, area.y + half_h, right.w, area.h - half_h)
    if n == 3:
        return [left, top_r, bot_r]
    return [Rect(area.x, area.y, half_w, half_h), top_r, Rect(area.x, area.y + half_h, half_w, area.h - half_h), bot_r]


def match(asks: list[str], windows: list[Win]) -> tuple[list[Win], list[str]]:
    """The window meant by each word ("canvas", "claude", "practice 6"), one window each. Returns (found, not found).
    A title has to hold every word of the ask; among those, one where the word is a part of the title in its own
    right ("... - Canvas - Google Chrome", "Claude") wins over a file that merely mentions it, then a window that
    isn't minimized, then the shortest title."""
    found: list[Win] = []
    missing: list[str] = []
    for ask in asks:
        words = [w for w in ask.lower().split() if w]
        hits = [w for w in windows if w not in found and words and all(x in w.title.lower() for x in words)]
        if not hits:
            missing.append(ask)
            continue
        def rank(w: Win, ask: str = ask) -> tuple:
            # "Canvas" as a part of the title in its own right (the site, the app) beats a file that only mentions it
            own = any(part.strip().lower().startswith(ask.lower()) for part in w.title.split(" - "))
            return (not own, w.minimized, len(w.title))

        found.append(min(hits, key=rank))
    return found, missing


def pick_screen(screens: list[Rect], windows: list[Win], want: str) -> int:
    """Which screen to lay out. "laptop" (the default) is the one the hub is not on, since the hub lives on his
    monitor; with one screen, or no hub open, it is the first. "monitor" is the one with the hub."""
    hub = next((w.screen for w in windows if w.title.startswith(HUB_TITLE)), None)
    if len(screens) < 2 or hub is None:
        return 0
    if want == "monitor":
        return hub
    return next(i for i in range(len(screens)) if i != hub)


class Desktop:
    """Windows only. Every method is safe to call elsewhere: it reports nothing open and moves nothing."""

    def __init__(self) -> None:
        self.ok = sys.platform == "win32"

    def _api(self):
        import ctypes  # noqa: PLC0415
        from ctypes import wintypes  # noqa: PLC0415

        user32, dwm = ctypes.windll.user32, ctypes.windll.dwmapi
        user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.IsIconic.argtypes = [wintypes.HWND]
        user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        user32.MonitorFromWindow.restype = wintypes.HMONITOR
        user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        dwm.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        return ctypes, wintypes, user32, dwm

    def _aware(self, user32):
        """Real pixels on every screen while we measure and move (laptop and monitor often scale differently).
        Returns the previous mode to put back, or None on a Windows too old to have it."""
        import ctypes  # noqa: PLC0415

        try:
            setter = user32.SetThreadDpiAwarenessContext
            setter.restype, setter.argtypes = ctypes.c_void_p, [ctypes.c_void_p]
            return setter(ctypes.c_void_p(-4))      # per-monitor aware, version 2
        except Exception:  # noqa: BLE001
            return None

    def screens(self) -> list[Rect]:
        """Each screen's usable area (without the taskbar), in a stable left-to-right order."""
        if not self.ok:
            return []
        ctypes, wintypes, user32, _ = self._api()
        old = self._aware(user32)
        out: list[tuple[int, Rect]] = []

        class Info(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

        proc_t = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

        def each(monitor, _dc, _rect, _param):
            info = Info()
            info.cbSize = ctypes.sizeof(Info)
            if user32.GetMonitorInfoW(wintypes.HMONITOR(monitor), ctypes.byref(info)):
                r = info.rcWork
                out.append((int(monitor), Rect(r.left, r.top, r.right - r.left, r.bottom - r.top)))
            return 1

        user32.EnumDisplayMonitors(None, None, proc_t(each), 0)
        if old:
            user32.SetThreadDpiAwarenessContext(old)
        out.sort(key=lambda m: (m[1].x, m[1].y))
        self._monitors = [m[0] for m in out]
        return [m[1] for m in out]

    def windows(self) -> list[Win]:
        """The ordinary windows he can see or has minimized, front to back. Titles only."""
        if not self.ok:
            return []
        ctypes, wintypes, user32, dwm = self._api()
        if not getattr(self, "_monitors", None):
            self.screens()
        out: list[Win] = []
        proc_t = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HWND, wintypes.LPARAM)

        def each(hwnd, _param):
            if not user32.IsWindowVisible(hwnd):
                return 1
            if user32.GetWindowLongW(hwnd, -20) & 0x00000080:      # a tool window (no taskbar button)
                return 1
            cloaked = wintypes.DWORD(0)
            dwm.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
            if cloaked.value:                                       # on another virtual desktop, or a hidden app frame
                return 1
            n = user32.GetWindowTextLengthW(hwnd)
            if n <= 0:
                return 1
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            title = buf.value.strip()
            if not title or title in SKIP_TITLES:
                return 1
            monitor = int(user32.MonitorFromWindow(hwnd, 2) or 0)
            screen = self._monitors.index(monitor) if monitor in self._monitors else 0
            out.append(Win(int(hwnd), title, screen, bool(user32.IsIconic(hwnd))))
            return 1

        user32.EnumWindows(proc_t(each), 0)
        return out

    def place(self, win: Win, rect: Rect) -> bool:
        """Put one window exactly there (restored first if it was minimized or maximized), on top, without stealing
        the keyboard from whatever he is typing in."""
        if not self.ok:
            return False
        ctypes, wintypes, user32, dwm = self._api()
        old = self._aware(user32)
        try:
            user32.ShowWindow(win.handle, 9)                        # SW_RESTORE
            outer, frame = wintypes.RECT(), wintypes.RECT()
            pad_l = pad_r = pad_b = 0
            if user32.GetWindowRect(win.handle, ctypes.byref(outer)) and \
                    dwm.DwmGetWindowAttribute(win.handle, 9, ctypes.byref(frame), ctypes.sizeof(frame)) == 0:
                # Windows draws an invisible border around most windows: without this the halves leave a gap
                pad_l, pad_r, pad_b = frame.left - outer.left, outer.right - frame.right, outer.bottom - frame.bottom
            flags = 0x0010 | 0x0040                                 # SWP_NOACTIVATE | SWP_SHOWWINDOW
            return bool(user32.SetWindowPos(win.handle, 0, rect.x - pad_l, rect.y, rect.w + pad_l + pad_r, rect.h + pad_b, flags))
        finally:
            if old:
                user32.SetThreadDpiAwarenessContext(old)
