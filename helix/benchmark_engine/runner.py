"""Benchmark comparison runner."""

from __future__ import annotations

from helix.benchmark_engine.collector import BenchmarkCollector
from helix.benchmark_engine.types import AttributionReport, BenchmarkResult
from helix.cache_engine.store import CacheStore
from helix.execution_optimizer.types import ExecutionDecisionType
from helix.graph_engine.graph import ComputationGraph
from helix.workflow.runner import WorkflowRunner
from helix.workflow.types import Workflow


class BenchmarkRunner:
    """Run baseline and optimized workflows and compute attribution."""

    def __init__(
        self,
        baseline_runner: WorkflowRunner,
        optimized_runner: WorkflowRunner,
        cost_table: dict[str, float],
    ) -> None:
        """Create a benchmark runner."""
        self.baseline_runner = baseline_runner
        self.optimized_runner = optimized_runner
        self.cost_table = cost_table

    def _clear_store(self) -> None:
        if isinstance(self.optimized_runner.optimizer.cache_store, CacheStore):
            self.optimized_runner.optimizer.cache_store.clear()
        graph = self.optimized_runner.optimizer.graph
        if isinstance(graph, ComputationGraph):
            with graph._connect() as conn:
                conn.execute("DELETE FROM graph_nodes")

    def _result_from_run(self, run, collector: BenchmarkCollector, mode: str) -> BenchmarkResult:
        return collector.finalize(run.run_id, run.workflow_id, mode, run.optimization_plan, self.cost_table)

    def _pct(self, saved: float, baseline: float) -> float:
        return (saved / baseline * 100.0) if baseline else 0.0

    def _increase_pct(self, optimized: float, baseline: float) -> float:
        return ((optimized - baseline) / baseline * 100.0) if baseline else 0.0

    def _regression_warnings(self, baseline: BenchmarkResult, optimized: BenchmarkResult) -> list[str]:
        warnings: list[str] = []
        if optimized.total_tokens > baseline.total_tokens:
            warnings.append(
                f"optimized tokens exceeded baseline by "
                f"{self._increase_pct(optimized.total_tokens, baseline.total_tokens):.1f}%"
            )
        if optimized.estimated_cost_usd > baseline.estimated_cost_usd:
            warnings.append(
                f"optimized cost exceeded baseline by "
                f"{self._increase_pct(optimized.estimated_cost_usd, baseline.estimated_cost_usd):.1f}%"
            )
        if optimized.total_latency_ms > baseline.total_latency_ms:
            warnings.append(
                f"optimized latency exceeded baseline by "
                f"{self._increase_pct(optimized.total_latency_ms, baseline.total_latency_ms):.1f}%"
            )
        if optimized.calls > baseline.calls:
            warnings.append(
                f"optimized calls exceeded baseline by "
                f"{self._increase_pct(optimized.calls, baseline.calls):.1f}%"
            )
        if optimized.optimization_overhead_tokens > optimized.tokens_saved_by_minimization:
            warnings.append(
                "minimization overhead exceeded savings "
                f"({optimized.optimization_overhead_tokens} overhead vs "
                f"{optimized.tokens_saved_by_minimization} removed)"
            )
        return warnings

    def run_comparison(self, workflow: Workflow, inputs: dict[str, str]) -> AttributionReport:
        """Run baseline, run optimized, and produce an AttributionReport."""
        self._clear_store()
        self.baseline_runner.benchmark_collector = BenchmarkCollector()
        baseline_run = self.baseline_runner.run(workflow, inputs)
        baseline = self._result_from_run(
            baseline_run, self.baseline_runner.benchmark_collector, "baseline"
        )
        self.optimized_runner.benchmark_collector = BenchmarkCollector()
        optimized_run = self.optimized_runner.run(workflow, inputs)
        optimized = self._result_from_run(
            optimized_run, self.optimized_runner.benchmark_collector, "optimized"
        )
        latency_saved = baseline.total_latency_ms - optimized.total_latency_ms
        cost_saved = baseline.estimated_cost_usd - optimized.estimated_cost_usd
        tokens_saved = baseline.total_tokens - optimized.total_tokens
        steps_reduced = baseline.steps_executed - optimized.steps_executed
        context_tokens = sum(
            base.input_tokens + base.output_tokens
            for base, opt in zip(baseline.per_step, optimized.per_step)
            if opt.cache_hit
        )
        graph_tokens = sum(
            base.input_tokens + base.output_tokens
            for base, opt in zip(baseline.per_step, optimized.per_step)
            if opt.graph_reuse
        )
        kv_tokens = sum(
            step.kv_estimate.prefix_overlap_tokens if step.kv_estimate else 0
            for step in optimized.per_step
            if step.decision == ExecutionDecisionType.EXECUTE
        )
        context = context_tokens / baseline.total_tokens * 100.0 if baseline.total_tokens else 0.0
        graph = graph_tokens / baseline.total_tokens * 100.0 if baseline.total_tokens else 0.0
        kv = kv_tokens / baseline.total_tokens * 100.0 if baseline.total_tokens else 0.0
        reusable_total = context + graph + kv
        if reusable_total > 100.0:
            scale = 100.0 / reusable_total
            context *= scale
            graph *= scale
            kv *= scale
        if tokens_saved <= 0 or cost_saved < 0 or latency_saved <= 0:
            step_reduction = 0.0
            context = 0.0
            graph = 0.0
            kv = 0.0
        else:
            step_reduction = max(0.0, 100.0 - context - kv - graph)
        report = AttributionReport(
            baseline=baseline,
            optimized=optimized,
            latency_saved_ms=latency_saved,
            latency_saved_pct=self._pct(latency_saved, baseline.total_latency_ms),
            cost_saved_usd=cost_saved,
            cost_saved_pct=self._pct(cost_saved, baseline.estimated_cost_usd),
            tokens_saved=tokens_saved,
            tokens_saved_pct=self._pct(tokens_saved, baseline.total_tokens),
            steps_reduced=steps_reduced,
            calls_avoided=baseline.calls - optimized.calls,
            tokens_avoided=tokens_saved,
            steps_eliminated=optimized.steps_skipped,
            partial_recomputation_steps=optimized.steps_cached + optimized.steps_graph_reused,
            context_reuse_pct=context,
            kv_simulation_pct=kv,
            graph_reuse_pct=graph,
            step_reduction_pct=step_reduction,
            warnings=self._regression_warnings(baseline, optimized),
        )
        report.validate()
        return report

    def run_real_comparison(
        self,
        workflow: Workflow,
        measured_inputs: dict[str, str],
        warmup_inputs: dict[str, str] | None = None,
    ) -> AttributionReport:
        """Run a real cold baseline and measured optimized run with optional optimizer warmup."""
        self._clear_store()
        self.baseline_runner.benchmark_collector = BenchmarkCollector()
        baseline_run = self.baseline_runner.run(workflow, measured_inputs)
        baseline = self._result_from_run(
            baseline_run, self.baseline_runner.benchmark_collector, "baseline"
        )

        if isinstance(self.optimized_runner.optimizer.cache_store, CacheStore):
            self.optimized_runner.optimizer.cache_store.clear()
        graph = self.optimized_runner.optimizer.graph
        if isinstance(graph, ComputationGraph):
            with graph._connect() as conn:
                conn.execute("DELETE FROM graph_nodes")
        if warmup_inputs is not None:
            self.optimized_runner.benchmark_collector = BenchmarkCollector()
            self.optimized_runner.run(workflow, warmup_inputs)

        self.optimized_runner.benchmark_collector = BenchmarkCollector()
        optimized_run = self.optimized_runner.run(workflow, measured_inputs)
        optimized = self._result_from_run(
            optimized_run, self.optimized_runner.benchmark_collector, "optimized"
        )

        latency_saved = baseline.total_latency_ms - optimized.total_latency_ms
        cost_saved = baseline.estimated_cost_usd - optimized.estimated_cost_usd
        tokens_saved = baseline.total_tokens - optimized.total_tokens
        steps_reduced = baseline.steps_executed - optimized.steps_executed
        calls_avoided = baseline.calls - optimized.calls
        steps_eliminated = optimized.steps_skipped
        partial_recomputation = optimized.steps_cached + optimized.steps_graph_reused

        context_tokens = sum(
            base.input_tokens + base.output_tokens
            for base, opt in zip(baseline.per_step, optimized.per_step)
            if opt.cache_hit
        )
        graph_tokens = sum(
            base.input_tokens + base.output_tokens
            for base, opt in zip(baseline.per_step, optimized.per_step)
            if opt.graph_reuse
        )
        if tokens_saved <= 0 or cost_saved < 0 or latency_saved <= 0:
            context = 0.0
            graph_pct = 0.0
            step_reduction = 0.0
        else:
            context = context_tokens / baseline.total_tokens * 100.0 if baseline.total_tokens else 0.0
            graph_pct = graph_tokens / baseline.total_tokens * 100.0 if baseline.total_tokens else 0.0
            step_reduction = max(0.0, 100.0 - context - graph_pct)

        report = AttributionReport(
            baseline=baseline,
            optimized=optimized,
            latency_saved_ms=latency_saved,
            latency_saved_pct=self._pct(latency_saved, baseline.total_latency_ms),
            cost_saved_usd=cost_saved,
            cost_saved_pct=self._pct(cost_saved, baseline.estimated_cost_usd),
            tokens_saved=tokens_saved,
            tokens_saved_pct=self._pct(tokens_saved, baseline.total_tokens),
            steps_reduced=steps_reduced,
            calls_avoided=calls_avoided,
            tokens_avoided=tokens_saved,
            steps_eliminated=steps_eliminated,
            partial_recomputation_steps=partial_recomputation,
            context_reuse_pct=context,
            kv_simulation_pct=0.0,
            graph_reuse_pct=graph_pct,
            step_reduction_pct=step_reduction,
            warnings=self._regression_warnings(baseline, optimized),
        )
        report.validate()
        return report
