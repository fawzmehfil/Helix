"""Benchmark metric collector."""

from __future__ import annotations

import datetime as dt
from typing import Optional

from helix.benchmark_engine.cost import estimate_cost_usd
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
        run=None,
    ) -> BenchmarkResult:
        """Compute aggregate benchmark metrics."""
        input_tokens = sum(step.input_tokens for step in self.steps)
        output_tokens = sum(step.output_tokens for step in self.steps)
        total_tokens = input_tokens + output_tokens
        estimated_cost = sum(
            step.estimated_cost_usd
            if step.estimated_cost_usd
            else estimate_cost_usd(step.model, step.input_tokens, step.output_tokens)
            for step in self.steps
        )
        if estimated_cost == 0.0 and cost_table:
            cost_per_1k = cost_table.get("fake", 0.0)
            estimated_cost = total_tokens / 1000.0 * cost_per_1k
        return BenchmarkResult(
            run_id=run_id,
            workflow_id=workflow_id,
            mode=mode,
            total_latency_ms=getattr(run, "total_latency_ms", sum(step.latency_ms for step in self.steps)),
            total_input_tokens=input_tokens,
            total_output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=estimated_cost,
            steps_executed=sum(1 for step in self.steps if step.decision == ExecutionDecisionType.EXECUTE),
            steps_cached=sum(1 for step in self.steps if step.cache_hit),
            steps_graph_reused=sum(1 for step in self.steps if step.graph_reuse),
            steps_skipped=sum(1 for step in self.steps if step.decision == ExecutionDecisionType.SKIP),
            calls=sum(step.call_count for step in self.steps),
            raw_input_tokens=sum(step.raw_input_tokens for step in self.steps),
            projected_input_tokens=sum(step.projected_input_tokens for step in self.steps),
            minimized_input_tokens=sum(step.minimized_input_tokens for step in self.steps),
            tokens_removed_by_projection=sum(
                step.tokens_removed_by_projection for step in self.steps
            ),
            optimization_overhead_tokens=sum(step.optimization_overhead_tokens for step in self.steps),
            net_tokens_saved_by_minimization=sum(
                step.net_tokens_saved_by_minimization for step in self.steps
            ),
            minimization_effective_steps=sum(1 for step in self.steps if step.minimization_effective),
            tokens_trimmed_by_budget=sum(step.tokens_trimmed_by_budget for step in self.steps),
            budget_applied_steps=sum(1 for step in self.steps if step.budget_applied),
            minimization_warnings=[
                warning
                for step in self.steps
                for warning in step.minimization_warnings
            ],
            tokens_saved_by_minimization=sum(step.tokens_saved_by_minimization for step in self.steps),
            net_token_change=sum(step.net_token_change for step in self.steps),
            semantic_cache_hits=sum(1 for step in self.steps if step.semantic_cache_hit),
            semantic_reuse_accepted=sum(1 for step in self.steps if step.semantic_reuse_accepted),
            semantic_reuse_rejected=sum(1 for step in self.steps if step.semantic_reuse_rejected),
            avg_similarity_score=(
                sum(step.similarity_score for step in self.steps if step.semantic_reuse_applied)
                / max(1, sum(1 for step in self.steps if step.semantic_reuse_applied))
            ),
            embedding_latency_ms=sum(step.embedding_latency_ms for step in self.steps),
            embedding_calls=sum(step.embedding_calls for step in self.steps),
            repair_attempts=sum(1 for step in self.steps if step.repair_attempted),
            repair_successes=sum(1 for step in self.steps if step.repair_successful),
            schema_validation_failures=sum(1 for step in self.steps if step.schema_validation_failed),
            per_step=list(self.steps),
            timestamp=dt.datetime.now(dt.UTC),
            sequential_estimated_latency_ms=getattr(run, "sequential_estimated_latency_ms", 0.0),
            actual_parallel_latency_ms=getattr(run, "actual_parallel_latency_ms", 0.0),
            critical_path_latency_ms=getattr(run, "critical_path_latency_ms", 0.0),
            parallel_speedup_factor=getattr(run, "parallel_speedup_factor", 1.0),
            max_concurrency=getattr(run, "max_concurrency", 1),
            parallel_steps_executed=getattr(run, "parallel_steps_executed", 0),
        )
