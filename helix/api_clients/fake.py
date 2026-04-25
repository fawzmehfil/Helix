"""Deterministic fake LLM client."""

from __future__ import annotations

import hashlib
import json
import time

from helix.tokenization import TokenCounter


class FakeLLMClient:
    """Deterministic fake LLM. Response = SHA-256 of messages JSON, truncated."""

    model_id: str = "fake"

    def __init__(self, sleep_ms: float = 50.0) -> None:
        """Create a fake client with simulated latency."""
        self.sleep_ms = sleep_ms
        self._token_counter = TokenCounter(self.model_id)

    def call(self, messages: list[dict], **kwargs) -> dict:
        """Return a deterministic normalized fake response."""
        if self.sleep_ms > 0:
            time.sleep(self.sleep_ms / 1000.0)
        payload = json.dumps(messages, sort_keys=True)
        content = self._structured_content(payload)
        if content is None:
            content = hashlib.sha256(payload.encode()).hexdigest()[:64]
        input_tokens = self._token_counter.count_messages(messages)
        return {
            "content": content,
            "input_tokens": input_tokens,
            "output_tokens": 20,
            "model": self.model_id,
            "finish_reason": "stop",
            "raw": {"messages_hash": content},
        }

    def _structured_content(self, payload: str) -> str | None:
        """Return compact deterministic JSON for JSON-oriented demo prompts."""
        text = payload.lower()
        if "doc_type" in text and "region" in text and "category" not in text:
            return (
                '{"doc_type":"invoice","irrelevant_notes":"internal routing memo with '
                'billing boilerplate and nonessential audit text","owner":"ops","priority":"normal",'
                '"region":"US"}'
            )
        if "category" in text and "confidence" in text and "valid" not in text:
            return (
                '{"category":"invoice","confidence":0.98,'
                '"routing_explanation":"standard accounts payable invoice workflow"}'
            )
        if "items" in text and "due_days" in text and "summary" not in text:
            due_days = 15 if "fifteen" in text or "15" in text else 30
            return (
                f'{{"audit_notes":"line item extraction included unchanged service details",'
                f'"changed_section":"quantity and payment terms",'
                f'"due_days":{due_days},"items":["imaging sensors","calibration visit"]}}'
            )
        if "valid" in text and "reason" in text:
            return '{"reason":"routing fields are consistent","valid":true}'
        if "summary" in text:
            return '{"summary":"invoice quantity and payment terms updated"}'
        return None

    def is_available(self) -> bool:
        """Return True because the fake client is always available."""
        return True
