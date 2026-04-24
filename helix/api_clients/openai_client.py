"""OpenAI LLM client."""

from __future__ import annotations

import os
import time
from typing import Optional

from helix.exceptions import LLMClientError


class OpenAIClient:
    """OpenAI chat completions adapter."""

    model_id: str

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
        min_interval_seconds: float = 0.2,
    ) -> None:
        """api_key defaults to OPENAI_API_KEY env var."""
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model_id = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.min_interval_seconds = min_interval_seconds
        self._last_call_at = 0.0

    def call(self, messages: list[dict], **kwargs) -> dict:
        """Call OpenAI and return a normalized response."""
        try:
            import openai
        except ImportError as exc:
            raise LLMClientError("openai package is not installed") from exc
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            wait = self.min_interval_seconds - (time.perf_counter() - self._last_call_at)
            if wait > 0:
                time.sleep(wait)
            started = time.perf_counter()
            try:
                client = openai.OpenAI(api_key=self.api_key, timeout=self.timeout_seconds)
                result = client.chat.completions.create(
                    model=self.model_id,
                    messages=messages,
                    **kwargs,
                )
                self._last_call_at = time.perf_counter()
                elapsed = (self._last_call_at - started) * 1000
                choice = result.choices[0]
                usage = result.usage
                return {
                    "content": choice.message.content or "",
                    "input_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
                    "output_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
                    "model": self.model_id,
                    "finish_reason": choice.finish_reason or "unknown",
                    "latency_ms": elapsed,
                    "raw": result.model_dump() if hasattr(result, "model_dump") else {},
                }
            except (openai.APIError, openai.APITimeoutError, openai.RateLimitError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                time.sleep(0.5 * (2**attempt))
        raise LLMClientError(str(last_error)) from last_error

    def is_available(self) -> bool:
        """Return True if openai package installed and API key present."""
        try:
            import openai  # noqa: F401
        except ImportError:
            return False
        return bool(self.api_key)
