"""Client protocol definitions."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    """Protocol for normalized LLM clients."""

    model_id: str

    def call(
        self,
        messages: list[dict],
        max_tokens: int = 1024,
        temperature: float = 0.0,
        **kwargs,
    ) -> dict:
        """Return a normalized response dict."""
        ...

    def is_available(self) -> bool:
        """Return True if client can make calls."""
        ...


@runtime_checkable
class ToolClient(Protocol):
    """Protocol for tool clients."""

    def call(self, tool_name: str, args: dict) -> dict:
        """Return a normalized tool response."""
        ...

