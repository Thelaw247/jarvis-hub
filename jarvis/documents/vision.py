"""Claude's vision for images and scanned pages (read_document): one short Haiku call per image."""
from __future__ import annotations

import base64
from collections.abc import Awaitable, Callable
from typing import Any

VISION_MODEL = "claude-haiku-5-5"


def make_vision(keyed: Any, client_factory: Callable[[str], Any] | None = None,
                model: str = VISION_MODEL) -> Callable[[bytes, str], Awaitable[str]]:
    def client(key: str) -> Any:
        if client_factory is not None:
            return client_factory(key)
        import anthropic  # noqa: PLC0415

        return anthropic.AsyncAnthropic(api_key=key, max_retries=1)

    async def vision(png: bytes, prompt: str) -> str:
        media = "image/png" if png[:4] == b"\x89PNG" else "image/jpeg"

        async def run(key: str) -> str:
            msg = await client(key).messages.create(
                model=model, max_tokens=2048,
                messages=[{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media,
                                                 "data": base64.b64encode(png).decode()}},
                    {"type": "text", "text": prompt}]}])
            return "".join(getattr(b, "text", "") for b in msg.content)

        return await keyed.call(run)

    return vision
