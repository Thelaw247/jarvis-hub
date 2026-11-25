"""Embedding models behind one small interface (MEMORY §7.4, §12).

Two spaces, because a query must be embedded by the same model that built the index:
- ``fast``  : a static embedding model for speculative hot-path recall while he is still talking (< 1 ms).
- ``index`` : a small int8 transformer for indexing, placement and deep recall (a few ms per text on CPU).

The real models are listed in REAL_MODELS and loaded only on Laptop B (nothing is downloaded in tests).
Tests and the sandbox benchmark use FakeEmbedder: deterministic, tiny, no network.
"""
from __future__ import annotations

import hashlib
import math
import re
import struct
from collections.abc import Sequence
from typing import Protocol, runtime_checkable


@runtime_checkable
class Embedder(Protocol):
    name: str
    dim: int

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Unit-length vectors, one per text. Synchronous (CPU models are)."""
        ...


# Picked per MEMORY §7.4 / §12. Latency on Laptop B is still to be measured (M1.1 exit).
REAL_MODELS: dict[str, dict[str, object]] = {
    "fast": {
        "model": "sentence-transformers/static-retrieval-mrl-en-v1",
        "dim": 256,  # Matryoshka: truncate 1024 -> 256 for speed; quality loss is small for retrieval
        "why": "static embeddings: no transformer at query time, ~0.1 ms per query on CPU",
        "alternative": "minishlab/potion-retrieval-32M (model2vec, 512d)",
    },
    "index": {
        "model": "BAAI/bge-small-en-v1.5",
        "dim": 384,
        "why": "small transformer, int8 ONNX (fastembed / optimum); good English retrieval for its size",
        "alternative": "intfloat/e5-small-v2 (384d)",
    },
    "rerank": {
        "model": "cross-encoder/ms-marco-MiniLM-L6-v2",
        "why": "optional cross-encoder rerank of the top ~30 in deep recall (MEMORY §7.4), int8 ONNX",
    },
}

_TOKEN = re.compile(r"[a-z0-9]+")


class FakeEmbedder:
    """Deterministic feature-hashing embedder for tests (words + character trigrams). No model, no network.

    Similar wording gives similar vectors, so ranking tests mean something; it is not a semantic model.
    """

    def __init__(self, dim: int = 64, name: str | None = None) -> None:
        self.dim = dim
        self.name = name or f"fake-hash-{dim}"

    def _features(self, text: str) -> list[str]:
        words = _TOKEN.findall(text.lower())
        feats = list(words)
        for w in words:
            padded = f"#{w}#"
            feats.extend(padded[i:i + 3] for i in range(len(padded) - 2))
        return feats

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        out = []
        for text in texts:
            vec = [0.0] * self.dim
            for f in self._features(text):
                h = hashlib.blake2b(f.encode(), digest_size=8).digest()
                idx = int.from_bytes(h[:4], "little") % self.dim
                vec[idx] += 1.0 if h[4] & 1 else -1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            out.append([v / norm for v in vec])
        return out


class SentenceTransformerEmbedder:  # pragma: no cover - needs the real model; run on Laptop B only
    """Adapter for a sentence-transformers model (static or transformer). Not exercised in the sandbox."""

    def __init__(self, model: str, dim: int | None = None) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model, device="cpu", truncate_dim=dim)
        self.name = f"{model}@{dim}" if dim else model
        self.dim = dim or int(self._model.get_sentence_embedding_dimension())

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vecs = self._model.encode(list(texts), normalize_embeddings=True, convert_to_numpy=True)
        return [v.tolist() for v in vecs]


def pack(vec: Sequence[float]) -> bytes:
    """float32 little-endian blob, the format vec0 stores."""
    return struct.pack(f"<{len(vec)}f", *vec)


def zeros(dim: int) -> bytes:
    return bytes(4 * dim)
