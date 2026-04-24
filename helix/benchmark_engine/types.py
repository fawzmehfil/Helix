"""Benchmark dataclasses."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

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
    per_step: list[StepResult]
    timestamp: dt.datetime


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
    context_reuse_pct: float
    kv_simulation_pct: float
    graph_reuse_pct: float
    step_reduction_pct: float

    def validate(self) -> None:
        """Assert percentages sum to ~100%."""
        total = (
            self.context_reuse_pct
            + self.kv_simulation_pct
            + self.graph_reuse_pct
            + self.step_reduction_pct
        )
        if self.tokens_saved == 0 and self.steps_reduced == 0 and self.latency_saved_ms <= 0:
            assert abs(total) <= 1.0, "attribution percentages must sum to 0 when no savings"
        else:
            assert abs(total - 100.0) <= 1.0, "attribution percentages must sum to approximately 100"

