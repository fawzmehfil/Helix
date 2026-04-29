"""Savings profiler data types."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NodeSavings:
    """Per-node savings attribution from benchmark results."""

    step_id: str
    decision: str
    calls_saved: int
    tokens_saved: int
    cost_saved_usd: float
    latency_saved_ms: float


@dataclass
class SavingsProfile:
    """Human-facing savings profile derived from an AttributionReport."""

    workflow_id: str
    baseline_calls: int
    baseline_tokens: int
    baseline_cost_usd: float
    baseline_latency_ms: float
    optimized_calls: int
    optimized_tokens: int
    optimized_cost_usd: float
    optimized_latency_ms: float
    calls_avoided: int
    cost_saved_usd: float
    cost_saved_pct: float
    tokens_saved: int
    tokens_saved_pct: float
    latency_saved_ms: float
    latency_saved_pct: float
    exact_cache_hits: int
    semantic_hits: int
    nodes_executed: int
    nodes_reused: int
    reuse_rate_pct: float
    recomputation_ratio_pct: float
    raw_input_tokens: int
    minimized_input_tokens: int
    context_reduction_pct: float
    top_savings_nodes: list[NodeSavings] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
