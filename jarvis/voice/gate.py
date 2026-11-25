"""When the voice window sends his mic to the core (v0.13.0): after "hey Jarvis", while he holds the talk key, or
always (the old behaviour, --listen always).

Nothing leaves the laptop while asleep (C23). The wake word is heard on the laptop itself; after it, the window
stays awake through the conversation: while the core says someone is talking, Jarvis is thinking or speaking, and
for a follow-up window after (so "and what about Friday?" needs no second "hey Jarvis"), then it goes back to
sleep. Jarvis speaking unprompted (a task's result) wakes it too, so "yes" or "stop" works without the wake word.

Pure logic with an injectable clock, so the timing is tested without a mic.
"""
from __future__ import annotations

import time
from collections.abc import Callable

FOLLOW_UP_S = 8.0       # after the last exchange: still listening this long without a new "hey Jarvis"
BUSY = {"listening", "thinking", "speaking"}


class Gate:
    def __init__(self, mode: str = "wake", *, follow_up_s: float = FOLLOW_UP_S,
                 clock: Callable[[], float] = time.monotonic) -> None:
        if mode not in ("wake", "ptt", "always"):
            raise ValueError(f"listen mode {mode!r}: wake, ptt or always")
        self.mode = mode
        self.follow_up_s = follow_up_s
        self.clock = clock
        self.awake = mode == "always"
        self.ptt = False
        self.busy = False
        self._quiet_since: float | None = None

    # ------------------------------------------------------------------ what happens
    def wake(self) -> list[dict]:
        """The wake word was heard (or Jarvis started speaking)."""
        if self.mode == "ptt" or self.awake:
            self._quiet_since = None if self.busy else self.clock()
            return []
        self.awake = True
        self._quiet_since = self.clock()
        return [{"type": "listen", "on": True}]

    def key(self, down: bool) -> list[dict]:
        if down == self.ptt:
            return []
        self.ptt = down
        out = [{"type": "ptt", "down": down}]
        if not down and self.mode == "wake":       # after a push-to-talk turn: carry on hands-free for a bit
            if not self.awake:
                out.append({"type": "listen", "on": True})
            self.awake = True
            self._quiet_since = self.clock()
        return out

    def core(self, state: str | None) -> None:
        """The core's orb state: someone talking / thinking / speaking keeps the window awake."""
        self.busy = state in BUSY
        if self.busy:
            self._quiet_since = None
        elif self._quiet_since is None:
            self._quiet_since = self.clock()

    def jarvis_audio(self) -> list[dict]:
        """Audio from the core: Jarvis is speaking, maybe unprompted. Listen, so he can answer or stop him."""
        if self.mode == "ptt":
            return []
        return self.wake()

    def tick(self) -> list[dict]:
        """Called with every mic frame: time to go back to sleep?"""
        if self.mode != "wake" or not self.awake or self.busy or self.ptt or self._quiet_since is None:
            return []
        if self.clock() - self._quiet_since >= self.follow_up_s:
            self.awake = False
            self._quiet_since = None
            return [{"type": "listen", "on": False}]
        return []

    # ------------------------------------------------------------------ asking
    @property
    def sending(self) -> bool:
        return self.ptt or self.awake

    @property
    def listening_for_wake(self) -> bool:
        return self.mode == "wake" and not self.sending
