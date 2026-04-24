"""Benchmark metric collector."""

from __future__ import annotations

import datetime as dt
from typing import Optional

from helix.execution_optimizer.types import ExecutionDecisionType, OptimizationPlan
from helix.workflow.types import StepResult
from helix.benchmark_engine.types import BenchmarkResult


class BenchmarkCollector:
    """Accumulates per-step metrics during a run. Thread-safe for v0 (no concurrency)."""

    def __init__(self) -> None:
        """Create an empty collector."""
        self.steps: list[StepResult] = []

    def record_step(self, step_result: StepResult) -> None:
        """Record one step result."""
        self.steps.append(step_result)

    def finalize(
        self,
        run_id: str,
        workflow_id: str,
        mode: str,
        optimization_plan: Optional[OptimizationPlan],
        cost_table: dict[str, float],
    ) -> BenchmarkResult:
        """Compute aggregate benchmark metrics."""
        input_tokens = sum(step.input_tokens for step in self.steps)
        output_tokens = sum(step.output_tokens for step in self.steps)
        total_tokens = input_tokens + output_tokens
        cost_per_1k = cost_table.get("fake", 0.0)
        return BenchmarkResult(
            run_id=run_id,
            workflow_id=workflow_id,
            mode=mode,
            total_latency_ms=sum(step.latency_ms for step in self.steps),
            total_input_tokens=input_tokens,
            total_output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=total_tokens / 1000.0 * cost_per_1k,
            steps_executed=sum(1 for step in self.steps if step.decision == ExecutionDecisionType.EXECUTE),
            steps_cached=sum(1 for step in self.steps if step.cache_hit),
            steps_graph_reused=sum(1 for step in self.steps if step.graph_reuse),
            steps_skipped=sum(1 for step in self.steps if step.decision == ExecutionDecisionType.SKIP),
            per_step=list(self.steps),
            timestamp=dt.datetime.utcnow(),
        )

