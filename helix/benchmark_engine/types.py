"""Benchmark dataclasses."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from helix.workflow.types import StepResult


@dataclass
class BenchmarkResult:
    """Aggregate benchmark metrics for one run."""

    run_id: str
    workflow_id: str
    mode: str
    total_latency_ms: float
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    steps_executed: int
    steps_cached: int
    steps_graph_reused: int
    steps_skipped: int
    calls: int
    raw_input_tokens: int
    projected_input_tokens: int
    minimized_input_tokens: int
    tokens_removed_by_projection: int
    optimization_overhead_tokens: int
    net_tokens_saved_by_minimization: int
    minimization_effective_steps: int
    tokens_trimmed_by_budget: int
    budget_applied_steps: int
    minimization_warnings: list[str]
    tokens_saved_by_minimization: int
    net_token_change: int
    semantic_cache_hits: int
    semantic_reuse_accepted: int
    semantic_reuse_rejected: int
    avg_similarity_score: float
    embedding_latency_ms: float
    embedding_calls: int
    repair_attempts: int
    repair_successes: int
    schema_validation_failures: int
    per_step: list[StepResult]
    timestamp: dt.datetime
    sequential_estimated_latency_ms: float = 0.0
    actual_parallel_latency_ms: float = 0.0
    critical_path_latency_ms: float = 0.0
    parallel_speedup_factor: float = 1.0
    max_concurrency: int = 1
    parallel_steps_executed: int = 0


@dataclass
class AttributionReport:
    """Baseline-vs-optimized benchmark attribution."""

    baseline: BenchmarkResult
    optimized: BenchmarkResult
    latency_saved_ms: float
    latency_saved_pct: float
    cost_saved_usd: float
    cost_saved_pct: float
    tokens_saved: int
    tokens_saved_pct: float
    steps_reduced: int
    calls_avoided: int
    tokens_avoided: int
    steps_eliminated: int
    partial_recomputation_steps: int
    context_reuse_pct: float
    kv_simulation_pct: float
    graph_reuse_pct: float
    step_reduction_pct: float
    semantic_calls_avoided: int = 0
    semantic_tokens_avoided: int = 0
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def validate(self) -> None:
        """Assert percentages sum to ~100%."""
        total = (
            self.context_reuse_pct
            + self.kv_simulation_pct
            + self.graph_reuse_pct
            + self.step_reduction_pct
        )
        if self.tokens_saved <= 0 or self.steps_reduced < 0 or self.latency_saved_ms <= 0:
            assert abs(total) <= 1.0, "attribution percentages must sum to 0 when no savings"
        else:
            assert abs(total - 100.0) <= 1.0, "attribution percentages must sum to approximately 100"
