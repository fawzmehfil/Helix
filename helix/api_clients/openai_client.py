"""OpenAI LLM client."""

from __future__ import annotations

import os
import time
from typing import Optional

from helix.exceptions import LLMClientError


class OpenAIClient:
    """OpenAI chat completions adapter."""

    model_id: str

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o") -> None:
        """api_key defaults to OPENAI_API_KEY env var."""
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model_id = model

    def call(self, messages: list[dict], **kwargs) -> dict:
        """Call OpenAI and return a normalized response."""
        try:
            import openai
        except ImportError as exc:
            raise LLMClientError("openai package is not installed") from exc
        try:
            started = time.perf_counter()
            client = openai.OpenAI(api_key=self.api_key)
            result = client.chat.completions.create(model=self.model_id, messages=messages, **kwargs)
            elapsed = (time.perf_counter() - started) * 1000
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
        except openai.APIError as exc:
            raise LLMClientError(str(exc)) from exc

    def is_available(self) -> bool:
        """Return True if openai package installed and API key present."""
        try:
            import openai  # noqa: F401
        except ImportError:
            return False
        return bool(self.api_key)

