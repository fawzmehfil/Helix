"""LLM client factory."""

from __future__ import annotations

from typing import Optional

from helix.api_clients.anthropic_client import AnthropicClient
from helix.api_clients.fake import FakeLLMClient
from helix.api_clients.openai_client import OpenAIClient
from helix.api_clients.protocols import LLMClient
from helix.exceptions import LLMClientError


class LLMClientFactory:
    """Create LLM clients by backend name."""

    @staticmethod
    def create(backend: str, model: Optional[str] = None, require_available: bool = False) -> LLMClient:
        """Create an LLM client, falling back to fake if unavailable."""
        if backend == "fake":
            return FakeLLMClient()
        if backend == "openai":
            client = OpenAIClient(model=model or "gpt-4o-mini")
            if client.is_available():
                return client
            if require_available:
                raise LLMClientError(
                    "OpenAI real benchmark skipped: OPENAI_API_KEY or openai package is missing."
                )
            return FakeLLMClient()
        if backend == "anthropic":
            client = AnthropicClient(model=model or "claude-3-haiku-20240307")
            if client.is_available():
                return client
            if require_available:
                raise LLMClientError(
                    "Anthropic real benchmark skipped: ANTHROPIC_API_KEY or anthropic package is missing."
                )
            return FakeLLMClient()
        return FakeLLMClient()
