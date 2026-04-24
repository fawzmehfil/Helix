"""Token pricing helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPricing:
    """Input and output token rates in USD per million tokens."""

    input_per_million: float
    output_per_million: float


MODEL_PRICING: dict[str, ModelPricing] = {
    "fake": ModelPricing(0.0, 0.0),
    "gpt-4o-mini": ModelPricing(0.15, 0.60),
    "gpt-4o": ModelPricing(2.50, 10.00),
    "claude-3-haiku-20240307": ModelPricing(0.25, 1.25),
    "claude-3-5-haiku-20241022": ModelPricing(0.80, 4.00),
    "claude-3-5-haiku-latest": ModelPricing(0.80, 4.00),
    "claude-3-5-sonnet-20241022": ModelPricing(3.00, 15.00),
}


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost for one call from model-specific token pricing."""
    pricing = MODEL_PRICING.get(model, MODEL_PRICING.get(model.split(":")[-1]))
    if pricing is None:
        pricing = ModelPricing(0.0, 0.0)
    return (
        input_tokens / 1_000_000.0 * pricing.input_per_million
        + output_tokens / 1_000_000.0 * pricing.output_per_million
    )
