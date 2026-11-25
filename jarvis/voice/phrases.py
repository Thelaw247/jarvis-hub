"""Phrase cache: frequent lines rendered once in the Jarvis voice, stored on disk, played from disk (F2.11).

Each line is keyed by a hash of (text, voice id, model, voice settings, output format), so changing the voice
or its settings makes every line miss and re-render; ``prune()`` deletes the old files. A manifest maps keys
to short ids the client can play ("play <id>", < 30 ms on Laptop A). Playing a cached line costs no credits.

Lines rotate (HUD v2 §9.4): every line type has several wordings, and ``PhraseBook.pick`` never repeats one of
the last five it used.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from collections import deque
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

PHRASES_V1: dict[str, tuple[str, ...]] = {
    "ack": ("On it.", "One moment.", "Checking.", "Give me a second.", "Right away."),
    "done": ("Done.", "That's done.", "All set."),
    "booked": ("Booked.", "It's in the calendar."),
    "sent": ("Sent.", "It's sent."),
    "morning": ("Morning.", "Good morning."),
    "evening": ("Evening.", "Good evening."),
    "back": ("Welcome back.",),
    "error": ("Sorry, I didn't catch that.", "I can't reach that right now.", "That didn't work. I'll try again."),
    "fixed": ("Timer off.", "What should change?", "Say send it to send it."),
}


class PhraseCache:
    def __init__(
        self,
        directory: Path,
        *,
        voice_id: str,
        model: str,
        settings: Mapping[str, Any],
        output_format: str,
        render: Callable[[str], Awaitable[bytes]],
    ) -> None:
        self.dir = Path(directory)
        self.voice_id, self.model, self.output_format = voice_id, model, output_format
        self.settings = dict(settings)
        self._render = render
        self._manifest_path = self.dir / "manifest.json"
        self._entries: dict[str, dict[str, Any]] = self._load()
        self._inflight: dict[str, asyncio.Future[bytes]] = {}
        self.renders = 0

    def _load(self) -> dict[str, dict[str, Any]]:
        try:
            return dict(json.loads(self._manifest_path.read_text(encoding="utf-8")).get("entries", {}))
        except (FileNotFoundError, ValueError):
            return {}

    def _save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self._manifest_path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"entries": self._entries}, indent=1, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self._manifest_path)

    def key(self, text: str) -> str:
        blob = json.dumps([text, self.voice_id, self.model, self.settings, self.output_format], sort_keys=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def id_for(self, text: str) -> str:
        return self.key(text)[:12]

    def has(self, text: str) -> bool:
        entry = self._entries.get(self.key(text))
        return entry is not None and (self.dir / entry["file"]).exists()

    def get(self, text: str) -> bytes | None:
        """T0. The rendered audio from disk, or None on a miss (~1 ms for a short line)."""
        entry = self._entries.get(self.key(text))
        if entry is None:
            return None
        try:
            return (self.dir / entry["file"]).read_bytes()
        except FileNotFoundError:
            return None

    async def ensure(self, text: str) -> bytes:
        """T2. Render once and store; concurrent calls for the same line share one render."""
        cached = self.get(text)
        if cached is not None:
            return cached
        k = self.key(text)
        fut = self._inflight.get(k)
        if fut is not None:
            return await fut
        fut = asyncio.get_running_loop().create_future()
        self._inflight[k] = fut
        try:
            audio = await self._render(text)
            self.renders += 1
            self.dir.mkdir(parents=True, exist_ok=True)
            name = f"{k[:16]}.pcm"
            tmp = self.dir / (name + ".tmp")
            tmp.write_bytes(audio)
            os.replace(tmp, self.dir / name)
            self._entries[k] = {"id": k[:12], "text": text, "file": name, "bytes": len(audio)}
            self._save()
            fut.set_result(audio)
            return audio
        except BaseException as exc:
            fut.set_exception(exc)
            fut.exception()  # mark retrieved
            raise
        finally:
            self._inflight.pop(k, None)

    async def warm(self, lines: Iterable[str]) -> int:
        """Render every missing line (at start-up, or after the voice changes). Returns how many rendered."""
        before = self.renders
        for text in lines:
            await self.ensure(text)
        return self.renders - before

    def prune(self, keep: Iterable[str] | None = None) -> int:
        """Delete entries made with another voice/settings (or not in ``keep``). Returns how many went."""
        wanted = {self.key(t) for t in keep} if keep is not None else None
        gone = 0
        for k, entry in list(self._entries.items()):
            current = self.key(entry["text"]) == k
            if not current or (wanted is not None and k not in wanted):
                (self.dir / entry["file"]).unlink(missing_ok=True)
                del self._entries[k]
                gone += 1
        if gone:
            self._save()
        return gone


class PhraseBook:
    """Rotating wordings per line type; never one of the last ``memory`` picks."""

    def __init__(self, groups: Mapping[str, Sequence[str]] | None = None, memory: int = 5) -> None:
        self.groups = {k: tuple(v) for k, v in (groups or PHRASES_V1).items()}
        self._recent: deque[str] = deque(maxlen=memory)
        self._turn = 0

    def all_lines(self) -> list[str]:
        return [line for lines in self.groups.values() for line in lines]

    def is_phrase(self, text: str) -> bool:
        return any(text in lines for lines in self.groups.values())

    def pick(self, group: str) -> str:
        options = self.groups[group]
        fresh = [o for o in options if o not in self._recent] or list(options)
        self._turn += 1
        choice = fresh[self._turn % len(fresh)]
        self._recent.append(choice)
        return choice
