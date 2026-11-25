"""ElevenLabs Flash v2.5 over one warm multi-context WebSocket (VOICE design).

One socket for the whole session, opened at start-up and kept alive with keep-alives, so a turn never pays
for a TLS + WebSocket handshake (~150-300 ms). Each turn is a context: text goes in as the talker streams it,
PCM 24 kHz comes back; barge-in closes the context. The voice id and model are config; the API key comes
through K1's ``KeyedClient.call`` (``mgr.client("elevenlabs")``) as the handshake header and is never logged.
The socket keeps the key it opened with; call ``reconnect()`` after a key swap. With no voice id set the client refuses to
start (C38/C39: one designed voice, never a clone, picked by De Wet).
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import itertools
import json
import logging
from collections.abc import AsyncIterator, Mapping
from typing import Any

from jarvis.voice.config import VoiceConfig
from jarvis.voice.ports import KeyedClient, WsConnect

log = logging.getLogger("jarvis.voice.tts")
_END = object()


async def _default_connect(url: str, headers: Mapping[str, str]) -> Any:
    import websockets  # imported lazily: tests and the sandbox run without it

    return await websockets.connect(url, additional_headers=dict(headers), max_size=None, open_timeout=5)


class ElevenLabsTTS:
    def __init__(
        self,
        config: VoiceConfig,
        keyed: KeyedClient,
        *,
        connect: WsConnect | None = None,
    ) -> None:
        self.config = config
        self.keyed = keyed
        self._connect = connect or _default_connect
        self._ws: Any = None
        self._queues: dict[str, asyncio.Queue[Any]] = {}
        self._dropped: set[str] = set()
        self._tasks: list[asyncio.Task[Any]] = []
        self._lock = asyncio.Lock()
        self._last_send = 0.0
        self._ids = itertools.count(1)
        self.connects = 0

    @property
    def url(self) -> str:
        c = self.config
        return (f"{c.tts_url}/v1/text-to-speech/{c.voice_id}/multi-stream-input?model_id={c.tts_model}"
                f"&output_format={c.tts_output_format}&inactivity_timeout={c.tts_inactivity_timeout_s}")

    async def start(self) -> None:
        """Open the socket now (warm) so the first turn doesn't pay for the handshake."""
        if not self.config.voice_id:
            raise RuntimeError("No voice id set: pick the designed Jarvis voice first (build plan 0.4).")
        async with self._lock:
            if self._ws is not None:
                return
            url = self.url
            # K1 leases the key for the handshake; a 401/403 there falls back to the previous key once.
            try:
                self._ws = await self.keyed.call(lambda key: self._connect(url, {"xi-api-key": key}))
            except Exception as exc:
                status = getattr(getattr(exc, "response", None), "status_code", "")
                log.warning("voice.tts_connect_failed", extra={"error": type(exc).__name__, "status": str(status),
                                                               "code": self.config.tts_model})
                raise
            self.connects += 1
            self._last_send = asyncio.get_running_loop().time()
            for t in self._tasks:  # a socket that closed by itself leaves its keep-alive behind
                t.cancel()
            self._tasks = [asyncio.create_task(self._receive()), asyncio.create_task(self._keepalive())]

    async def reconnect(self) -> None:
        """Re-open with the current key (K1 calls this after a key swap)."""
        await self._drop_socket()
        await self.start()

    async def _send(self, msg: Mapping[str, Any]) -> None:
        if self._ws is None:
            await self.start()
        await self._ws.send(json.dumps(msg))
        self._last_send = asyncio.get_running_loop().time()

    async def open(self, context_id: str) -> None:
        """T1. Start a context; the first message carries the voice settings."""
        self._queues[context_id] = asyncio.Queue()
        self._dropped.discard(context_id)
        await self._send({"text": " ", "context_id": context_id, "voice_settings": dict(self.config.voice_settings)})

    async def send(self, context_id: str, text: str) -> None:
        """T1. Queue text for speech; ``flush`` makes ElevenLabs speak it without waiting for more."""
        if context_id in self._dropped:
            return
        await self._send({"text": text if text.endswith(" ") else text + " ", "context_id": context_id,
                          "flush": True})

    async def flush(self, context_id: str) -> None:
        """End of input for this context: speak what's left, then the context closes (isFinal)."""
        if context_id in self._dropped:
            return
        await self._send({"context_id": context_id, "flush": True})
        await self._send({"context_id": context_id, "close_context": True})

    async def cancel(self, context_id: str) -> None:
        """Barge-in: stop generating for this context and drop anything still to come."""
        self._dropped.add(context_id)
        q = self._queues.pop(context_id, None)
        if q is not None:
            q.put_nowait(_END)
        if self._ws is not None:
            with contextlib.suppress(Exception):
                await self._send({"context_id": context_id, "close_context": True})

    async def audio(self, context_id: str) -> AsyncIterator[bytes]:
        q = self._queues.get(context_id)
        if q is None:
            return
        while True:
            item = await q.get()
            if item is _END:
                return
            yield item

    async def synthesize(self, text: str) -> bytes:
        """T2. Render a whole line (phrase cache) on its own context of the same socket."""
        ctx = f"render-{next(self._ids)}"
        await self.open(ctx)
        await self.send(ctx, text)
        await self.flush(ctx)
        return b"".join([chunk async for chunk in self.audio(ctx)])

    async def _receive(self) -> None:
        try:
            while True:
                msg = json.loads(await self._ws.recv())
                if (msg.get("error") or msg.get("message")) and not msg.get("audio"):
                    err = str(msg.get("error") or msg.get("message"))
                    log.warning("voice.tts_error", extra={"code": err.replace(" ", "_")[:60], "reason": err})
                ctx = msg.get("contextId") or msg.get("context_id")
                q = self._queues.get(ctx) if ctx is not None else None
                if q is None:
                    continue
                if msg.get("audio"):
                    q.put_nowait(base64.b64decode(msg["audio"]))
                if msg.get("isFinal") or msg.get("is_final"):
                    q.put_nowait(_END)
                    self._queues.pop(ctx, None)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            ws = self._ws
            code, reason = getattr(ws, "close_code", None), getattr(ws, "close_reason", None)
            log.warning("voice.tts_closed", extra={"code": str(code if code is not None else type(exc).__name__),
                                                   "reason": reason or ""})
            for q in self._queues.values():
                q.put_nowait(_END)
            self._queues.clear()
            self._ws = None

    async def _keepalive(self) -> None:
        """Keep open contexts alive during long LLM pauses. Every message on this socket needs a context_id (one
        without closes the socket), so with no context open nothing is sent: an idle socket may close, and the
        pipeline re-opens it as soon as he starts talking (TtsProcessor._warm)."""
        loop = asyncio.get_running_loop()
        while True:
            await asyncio.sleep(self.config.tts_keepalive_s / 2)
            if self._ws is None or loop.time() - self._last_send < self.config.tts_keepalive_s:
                continue
            for ctx in list(self._queues):
                with contextlib.suppress(Exception):
                    await self._send({"context_id": ctx, "text": ""})

    async def _drop_socket(self) -> None:
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await t
        self._tasks = []
        ws, self._ws = self._ws, None
        if ws is not None:
            with contextlib.suppress(Exception):
                await ws.close()

    async def aclose(self) -> None:
        await self._drop_socket()


KEY_SWAPS = frozenset({"made_live", "replaced", "fell_back"})  # K1 audit names after which the live key is another one


async def follow_keys(tts: ElevenLabsTTS, events: AsyncIterator[Any], provider: str = "elevenlabs") -> None:
    """Re-open the warm socket whenever the ElevenLabs key is promoted or falls back (K1's `keys.updated`).

    `events`: the core's `bus.subscribe(["keys.updated"])` (anything that yields events with `.data`, or the data
    dicts themselves). Run it as a task beside the pipeline; a failed reconnect is retried on the next send."""
    async for event in events:
        data = getattr(event, "data", event) or {}
        if data.get("row", {}).get("id") == provider and (data.get("audit") or {}).get("what") in KEY_SWAPS:
            with contextlib.suppress(Exception):
                await tts.reconnect()
