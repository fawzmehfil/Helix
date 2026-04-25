"""Provider-aligned token counting helpers."""

from __future__ import annotations

import json
from typing import Any


def _text_token_estimate(text: str) -> int:
    return max(1, round(len(text) / 4)) if text else 0


class TokenCounter:
    """Count tokens for the message shape Helix sends to providers."""

    def __init__(self, model_id: str = "fake") -> None:
        self.model_id = model_id

    def count_messages(self, messages: list[dict[str, Any]]) -> int:
        """Return input tokens for provider message payloads."""
        model = self.model_id.lower()
        if model == "fake":
            return round(sum(len(str(m.get("content", "")).split()) for m in messages) * 1.3)
        if "gpt" in model or "openai" in model:
            return self._count_openai_messages(messages)
        if "claude" in model or "anthropic" in model:
            return self._count_anthropic_messages(messages)
        return self._count_serialized_messages(messages)

    def count_text(self, text: str) -> int:
        """Return output-text tokens using the provider tokenizer when available."""
        model = self.model_id.lower()
        if model == "fake":
            return round(len(text.split()) * 1.3)
        if "gpt" in model or "openai" in model:
            try:
                import tiktoken

                encoding = tiktoken.encoding_for_model(self.model_id)
                return len(encoding.encode(text))
            except Exception:
                return _text_token_estimate(text)
        return _text_token_estimate(text)

    def _count_openai_messages(self, messages: list[dict[str, Any]]) -> int:
        try:
            import tiktoken

            try:
                encoding = tiktoken.encoding_for_model(self.model_id)
            except KeyError:
                encoding = tiktoken.get_encoding("o200k_base")
            tokens_per_message = 3
            tokens_per_name = 1
            total = 3
            for message in messages:
                total += tokens_per_message
                for key, value in message.items():
                    total += len(encoding.encode(str(value)))
                    if key == "name":
                        total += tokens_per_name
            return total
        except Exception:
            return self._count_serialized_messages(messages)

    def _count_anthropic_messages(self, messages: list[dict[str, Any]]) -> int:
        system = "\n".join(
            str(message.get("content", "")) for message in messages if message.get("role") == "system"
        )
        user_messages = [message for message in messages if message.get("role") != "system"]
        payload = {
            "system": system or None,
            "messages": user_messages,
        }
        return _text_token_estimate(json.dumps(payload, separators=(",", ":"), sort_keys=True))

    def _count_serialized_messages(self, messages: list[dict[str, Any]]) -> int:
        return _text_token_estimate(json.dumps(messages, separators=(",", ":"), sort_keys=True))
