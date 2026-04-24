"""Deterministic fake LLM client."""

from __future__ import annotations

import hashlib
import json
import time


class FakeLLMClient:
    """Deterministic fake LLM. Response = SHA-256 of messages JSON, truncated."""

    model_id: str = "fake"

    def __init__(self, sleep_ms: float = 50.0) -> None:
        """Create a fake client with simulated latency."""
        self.sleep_ms = sleep_ms

    def call(self, messages: list[dict], **kwargs) -> dict:
        """Return a deterministic normalized fake response."""
        if self.sleep_ms > 0:
            time.sleep(self.sleep_ms / 1000.0)
        payload = json.dumps(messages, sort_keys=True)
        content = hashlib.sha256(payload.encode()).hexdigest()[:64]
        input_tokens = round(sum(len(str(m.get("content", "")).split()) for m in messages) * 1.3)
        return {
            "content": content,
            "input_tokens": input_tokens,
            "output_tokens": 20,
            "model": self.model_id,
            "finish_reason": "stop",
            "raw": {"messages_hash": content},
        }

    def is_available(self) -> bool:
        """Return True because the fake client is always available."""
        return True

