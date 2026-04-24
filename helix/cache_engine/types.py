"""Cache types and keys."""

from __future__ import annotations

import datetime as dt
import hashlib
from dataclasses import dataclass
from typing import Any, Optional

from helix.context_engine.types import ContextBlock


@dataclass
class CacheEntry:
    """Persistent cached response entry."""

    key: str
    step_id: str
    run_id: str
    response: dict[str, Any]
    input_tokens: int
    output_tokens: int
    latency_ms: float
    created_at: dt.datetime
    expires_at: Optional[dt.datetime]
    hit_count: int = 0


class CacheKey:
    """Deterministic composition of input block hashes."""

    def __init__(self, blocks: list[ContextBlock], model: str) -> None:
        """Create a cache key for blocks and model."""
        self.blocks = blocks
        self.model = model
        joined = "|".join([model, *[block.block_hash for block in blocks]])
        self._key = hashlib.sha256(joined.encode("utf-8")).hexdigest()

    @property
    def key(self) -> str:
        """Returns final hex string used as the DB key."""
        return self._key

    def __str__(self) -> str:
        """Return the cache key string."""
        return self.key

    def __eq__(self, other: object) -> bool:
        """Compare cache keys by final key string."""
        return isinstance(other, CacheKey) and self.key == other.key

    def __hash__(self) -> int:
        """Hash by final key string."""
        return hash(self.key)


@dataclass
class CachePolicy:
    """Cache behavior settings."""

    enabled: bool = True
    ttl_seconds: Optional[int] = 86400
    max_entries: int = 10_000
    eviction: str = "lru"
    invalidate_on_model_change: bool = True

