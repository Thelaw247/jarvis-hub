"""Jarvis memory (M1.1): one SQLite file (jarvis.db) with FTS5 + sqlite-vec, the Life Tree, audit, undo and
forget, behind a small swappable interface. Design: docs/design/JARVIS_DESIGN_MEMORY.md, ..._LIFE_TREE.md.
"""
from .embeddings import REAL_MODELS, Embedder, FakeEmbedder
from .interface import Memory
from .model import (
                    AddResult,
                    ChangeResult,
                    ClaimIn,
                    ClaimType,
                    EpisodeIn,
                    ForgetResult,
                    Hit,
                    Kind,
                    NowContext,
                    PlaceResult,
                    Trust,
                    UndoResult,
)
from .store import MemoryStore
from .trust import TrustError
from .undo import UndoError

__all__ = [
    "REAL_MODELS", "AddResult", "ChangeResult", "ClaimIn", "ClaimType", "Embedder", "EpisodeIn", "FakeEmbedder",
    "ForgetResult", "Hit", "Kind", "Memory", "MemoryStore", "NowContext", "PlaceResult", "Trust", "TrustError",
    "UndoError", "UndoResult",
]
