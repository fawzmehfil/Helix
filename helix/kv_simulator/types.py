"""KV simulation types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ModelSpec:
    """Model throughput and cost assumptions."""

    model_id: str
    tokens_per_second: float
    cache_hit_multiplier: float
    cost_per_1k_input_tokens: float
    cost_per_1k_output_tokens: float


@dataclass
class KVReuseEstimate:
    """Estimated savings from prefix KV reuse."""

    step_id: str
    prefix_overlap_tokens: int
    reused_fraction: float
    estimated_time_saved_ms: float
    estimated_cost_saved_usd: float
    model_id: str

