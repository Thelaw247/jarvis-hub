"""Sentence chunker: decides when LLM text is handed to TTS (VOICE design, speaking rules).

First chunk: at the first ``. ! ? , ;`` once there are >= 6 words, or at 12 words with no punctuation, so
TTS starts on a short opening clause. Later chunks: at sentence ends. ``flush()`` at the end of the turn.
"""

from __future__ import annotations

import re

from jarvis.voice.config import SpeakingRules

_SENTENCE_END = re.compile(r"[.!?](?=\s|$)")
_CLAUSE_END = re.compile(r"[.!?,;](?=\s|$)")


class Chunker:
    """T1 hot path; pure string work, microseconds per token."""

    def __init__(self, rules: SpeakingRules | None = None) -> None:
        self._rules = rules or SpeakingRules()
        self._buf = ""
        self._first_sent = False

    def feed(self, text: str) -> list[str]:
        """Add streamed text; return any chunks that are ready to speak."""
        self._buf += text
        out: list[str] = []
        while True:
            chunk = self._take()
            if chunk is None:
                return out
            out.append(chunk)

    def flush(self) -> list[str]:
        rest = self._buf.strip()
        self._buf = ""
        return [rest] if rest else []

    def _take(self) -> str | None:
        if not self._first_sent:
            for m in _CLAUSE_END.finditer(self._buf):
                if len(self._buf[: m.end()].split()) >= self._rules.first_chunk_min_words:
                    return self._cut(m.end())
            words = self._buf.split()
            # only cut on whole words: the last word may still be streaming
            if len(words) > self._rules.first_chunk_max_words or (
                len(words) == self._rules.first_chunk_max_words and self._buf.endswith((" ", "\n"))
            ):
                idx = _nth_word_end(self._buf, self._rules.first_chunk_max_words)
                return self._cut(idx)
            return None
        m = _SENTENCE_END.search(self._buf)
        return self._cut(m.end()) if m else None

    def _cut(self, idx: int) -> str:
        chunk, self._buf = self._buf[:idx].strip(), self._buf[idx:]
        self._first_sent = True
        return chunk


def _nth_word_end(text: str, n: int) -> int:
    count = 0
    for m in re.finditer(r"\S+", text):
        count += 1
        if count == n:
            return m.end()
    return len(text)
