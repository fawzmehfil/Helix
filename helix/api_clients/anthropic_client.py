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
        model: str = "claude-3-haiku-20240307",
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
        min_interval_seconds: float = 0.2,
    ) -> None:
        """api_key defaults to ANTHROPIC_API_KEY env var."""
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model_id = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.min_interval_seconds = min_interval_seconds
        self._last_call_at = 0.0

    def call(self, messages: list[dict], **kwargs) -> dict:
        """Call Anthropic and return a normalized response."""
        try:
            import anthropic
        except ImportError as exc:
            raise LLMClientError("anthropic package is not installed") from exc
        system = "\n".join(str(m.get("content", "")) for m in messages if m.get("role") == "system")
        user_messages = [m for m in messages if m.get("role") != "system"]
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            wait = self.min_interval_seconds - (time.perf_counter() - self._last_call_at)
            if wait > 0:
                time.sleep(wait)
            started = time.perf_counter()
            try:
                client = anthropic.Anthropic(api_key=self.api_key, timeout=self.timeout_seconds)
                result = client.messages.create(
                    model=self.model_id,
                    system=system or None,
                    messages=user_messages,
                    max_tokens=kwargs.pop("max_tokens", 256),
                    **kwargs,
                )
                self._last_call_at = time.perf_counter()
                elapsed = (self._last_call_at - started) * 1000
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
            except (anthropic.APIError, anthropic.APITimeoutError, anthropic.RateLimitError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                time.sleep(0.5 * (2**attempt))
        raise LLMClientError(str(last_error)) from last_error

    def is_available(self) -> bool:
        """Return True if anthropic package installed and API key present."""
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return bool(self.api_key)
