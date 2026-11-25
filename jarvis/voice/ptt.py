"""Push-to-talk (v0.13.0): hold a key anywhere in Windows while you talk; letting go ends the turn at once.

The key is Right Ctrl unless JARVIS_PTT_KEY names another (pynput's names: ctrl_r, alt_r, f13, caps_lock...).
pynput watches the keyboard globally without admin rights and without blocking the key for other apps. Key repeat
while held is ignored. The callbacks hop onto the voice window's event loop.
"""
from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from typing import Any

DEFAULT_KEY = "ctrl_r"


def key_name() -> str:
    return (os.environ.get("JARVIS_PTT_KEY") or DEFAULT_KEY).strip().lower()


def label(name: str) -> str:
    return {"ctrl_r": "Right Ctrl", "alt_r": "Right Alt", "ctrl_l": "Left Ctrl", "caps_lock": "Caps Lock"}.get(
        name, name.replace("_", " ").title())


class PushToTalk:
    def __init__(self, loop: asyncio.AbstractEventLoop, on_change: Callable[[bool], Any], name: str | None = None):
        from pynput import keyboard  # noqa: PLC0415

        self._kb = keyboard
        self.name = name or key_name()
        self.key = getattr(keyboard.Key, self.name, None) or keyboard.KeyCode.from_char(self.name[:1])
        self._loop = loop
        self._on_change = on_change
        self.held = False
        self._listener = keyboard.Listener(on_press=self._press, on_release=self._release)

    def start(self) -> None:
        self._listener.start()

    def stop(self) -> None:
        self._listener.stop()

    def _matches(self, key: Any) -> bool:
        return key == self.key

    def _press(self, key: Any) -> None:
        if self._matches(key) and not self.held:
            self.held = True
            self._loop.call_soon_threadsafe(self._on_change, True)

    def _release(self, key: Any) -> None:
        if self._matches(key) and self.held:
            self.held = False
            self._loop.call_soon_threadsafe(self._on_change, False)


def available() -> bool:
    try:
        import pynput  # noqa: F401, PLC0415
    except Exception:  # noqa: BLE001 - no display/keyboard backend counts as unavailable too
        return False
    return True
