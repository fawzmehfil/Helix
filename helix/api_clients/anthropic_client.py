"""Anthropic LLM client."""

from __future__ import annotations

import os
import time
from typing import Optional

from helix.exceptions import LLMClientError


class AnthropicClient:
    """Anthropic messages adapter."""

    model_id: str

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20241022",
    ) -> None:
        """api_key defaults to ANTHROPIC_API_KEY env var."""
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model_id = model

    def call(self, messages: list[dict], **kwargs) -> dict:
        """Call Anthropic and return a normalized response."""
        try:
            import anthropic
        except ImportError as exc:
            raise LLMClientError("anthropic package is not installed") from exc
        try:
            system = "\n".join(str(m.get("content", "")) for m in messages if m.get("role") == "system")
            user_messages = [m for m in messages if m.get("role") != "system"]
            started = time.perf_counter()
            client = anthropic.Anthropic(api_key=self.api_key)
            result = client.messages.create(
                model=self.model_id,
                system=system or None,
                messages=user_messages,
                max_tokens=kwargs.pop("max_tokens", 1024),
                **kwargs,
            )
            elapsed = (time.perf_counter() - started) * 1000
            content = result.content[0].text if result.content else ""
            return {
                "content": content,
                "input_tokens": int(getattr(result.usage, "input_tokens", 0) or 0),
                "output_tokens": int(getattr(result.usage, "output_tokens", 0) or 0),
                "model": self.model_id,
                "finish_reason": getattr(result, "stop_reason", "unknown") or "unknown",
                "latency_ms": elapsed,
                "raw": result.model_dump() if hasattr(result, "model_dump") else {},
            }
        except anthropic.APIError as exc:
            raise LLMClientError(str(exc)) from exc

    def is_available(self) -> bool:
        """Return True if anthropic package installed and API key present."""
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return bool(self.api_key)

