"""Plain settings he sets from the hub that aren't secrets (data\\settings.json on Laptop B).

First one: the ElevenLabs voice ID (C38/C39: one voice, made with Voice Design). A voice ID isn't a key, so it
lives here and can be shown back; keys stay in Credential Manager (jarvis.secrets). The voice pipeline reads it
with `voice_id()` when it opens its TTS connection.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

VOICE_ID = re.compile(r"[A-Za-z0-9]{10,40}")  # ElevenLabs voice IDs are 20 letters and digits


class CoreSettings:
    def __init__(self, path: Path) -> None:
        self.path = path

    def read(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def voice_id(self) -> str:
        value = self.read().get("voice_id", "")
        return value if isinstance(value, str) and VOICE_ID.fullmatch(value) else ""

    def set_voice_id(self, value: str) -> str:
        """Save the voice ID ("" clears it). Raises ValueError when it doesn't look like one."""
        value = (value or "").strip()
        if value and not VOICE_ID.fullmatch(value):
            raise ValueError("That doesn't look like an ElevenLabs voice ID (about 20 letters and digits).")
        data = self.read()
        if value:
            data["voice_id"] = value
        else:
            data.pop("voice_id", None)
        self._write(data)
        return value

    def hub(self) -> dict:
        """His Controls choices (theme, motion, how chatty…), saved so they survive a restart (v0.12.4)."""
        data = self.read().get("hub", {})
        return data if isinstance(data, dict) else {}

    def set_hub(self, name: str, value: object) -> None:
        data = self.read()
        hub = data.get("hub") if isinstance(data.get("hub"), dict) else {}
        hub[name] = value
        data["hub"] = hub
        self._write(data)

    def public(self) -> dict:
        return {"voice_id": self.voice_id()}

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".settings-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, self.path)
