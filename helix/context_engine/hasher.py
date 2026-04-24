"""Semantic hashing helpers."""

from __future__ import annotations

import hashlib
import json

from helix.context_engine.types import ContextBlock


class SemanticHasher:
    """SHA-256 based semantic hasher for v0."""

    def hash_text(self, text: str) -> str:
        """SHA-256 hex digest of normalized (stripped, lowercased) text."""
        return hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()

    def hash_blocks(self, blocks: list[ContextBlock]) -> str:
        """Composite hash of a sequence of blocks (order-sensitive)."""
        return hashlib.sha256("|".join(block.block_hash for block in blocks).encode()).hexdigest()

    def hash_messages(self, messages: list[dict]) -> str:
        """Hash a list of OpenAI-style message dicts."""
        return self.hash_text(json.dumps(messages, sort_keys=True))

