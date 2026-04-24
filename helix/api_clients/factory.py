"""LLM client factory."""

from __future__ import annotations

from typing import Optional

from helix.api_clients.anthropic_client import AnthropicClient
from helix.api_clients.fake import FakeLLMClient
from helix.api_clients.openai_client import OpenAIClient
from helix.api_clients.protocols import LLMClient


class LLMClientFactory:
    """Create LLM clients by backend name."""

    @staticmethod
    def create(backend: str, model: Optional[str] = None) -> LLMClient:
        """Create an LLM client, falling back to fake if unavailable."""
        if backend == "fake":
            return FakeLLMClient()
        if backend == "openai":
            client = OpenAIClient(model=model or "gpt-4o")
            return client if client.is_available() else FakeLLMClient()
        if backend == "anthropic":
            client = AnthropicClient(model=model or "claude-3-5-sonnet-20241022")
            return client if client.is_available() else FakeLLMClient()
        return FakeLLMClient()

