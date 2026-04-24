"""Echo tool client."""

from __future__ import annotations


class EchoToolClient:
    """Returns args as result. Used for testing."""

    def call(self, tool_name: str, args: dict) -> dict:
        """Return the provided args as the tool result."""
        return {"result": args, "latency_ms": 0.0, "tool_name": tool_name}

