"""Savings profile analysis built on benchmark reports."""

from __future__ import annotations

from helix.benchmark_engine.types import AttributionReport
from helix.execution_optimizer.types import ExecutionDecisionType
from helix.profiler.types import NodeSavings, SavingsProfile


class SavingsProfiler:
    """Build a savings profile from benchmark_engine output."""

    def analyze(self, report: AttributionReport) -> SavingsProfile:
        """Return a savings profile derived only from an AttributionReport."""
        optimized = report.optimized
        total_nodes = (
            optimized.steps_executed
            + optimized.steps_cached
            + optimized.steps_graph_reused
            + optimized.steps_skipped
        )
        reused_nodes = (
            optimized.steps_cached + optimized.steps_graph_reused + optimized.steps_skipped
        )
        exact_cache_hits = max(optimized.steps_cached - optimized.semantic_cache_hits, 0)
        reuse_rate = reused_nodes / total_nodes * 100.0 if total_nodes else 0.0
        recomputation_ratio = optimized.steps_executed / total_nodes * 100.0 if total_nodes else 0.0
        context_reduction = (
            optimized.net_tokens_saved_by_minimization / optimized.raw_input_tokens * 100.0
            if optimized.raw_input_tokens
            else 0.0
        )
        return SavingsProfile(
            workflow_id=report.baseline.workflow_id,
            baseline_calls=report.baseline.calls,
            baseline_tokens=report.baseline.total_tokens,
            baseline_cost_usd=report.baseline.estimated_cost_usd,
            baseline_latency_ms=report.baseline.total_latency_ms,
            optimized_calls=optimized.calls,
            optimized_tokens=optimized.total_tokens,
            optimized_cost_usd=optimized.estimated_cost_usd,
            optimized_latency_ms=optimized.total_latency_ms,
            calls_avoided=report.calls_avoided,
            cost_saved_usd=report.cost_saved_usd,
            cost_saved_pct=report.cost_saved_pct,
            tokens_saved=report.tokens_saved,
            tokens_saved_pct=report.tokens_saved_pct,
            latency_saved_ms=report.latency_saved_ms,
            latency_saved_pct=report.latency_saved_pct,
            exact_cache_hits=exact_cache_hits,
            semantic_hits=optimized.semantic_cache_hits,
            nodes_executed=optimized.steps_executed,
            nodes_reused=reused_nodes,
            reuse_rate_pct=reuse_rate,
            recomputation_ratio_pct=recomputation_ratio,
            raw_input_tokens=optimized.raw_input_tokens,
            minimized_input_tokens=optimized.minimized_input_tokens,
            context_reduction_pct=max(context_reduction, 0.0),
            top_savings_nodes=self._top_savings_nodes(report),
            recommendations=self._recommendations(report, reuse_rate),
            warnings=report.warnings,
            notes=report.notes,
        )

    def _top_savings_nodes(self, report: AttributionReport) -> list[NodeSavings]:
        nodes: list[NodeSavings] = []
        for baseline, optimized in zip(report.baseline.per_step, report.optimized.per_step):
            calls_saved = max(baseline.call_count - optimized.call_count, 0)
            tokens_saved = max(
                (baseline.input_tokens + baseline.output_tokens)
                - (optimized.input_tokens + optimized.output_tokens),
                0,
            )
            cost_saved = max(baseline.estimated_cost_usd - optimized.estimated_cost_usd, 0.0)
            latency_saved = max(baseline.latency_ms - optimized.latency_ms, 0.0)
            if self._is_savings_node(optimized.decision, calls_saved):
                nodes.append(
                    NodeSavings(
                        step_id=optimized.step_id,
                        decision=optimized.decision.value,
                        calls_saved=calls_saved,
                        tokens_saved=tokens_saved,
                        cost_saved_usd=cost_saved,
                        latency_saved_ms=latency_saved,
                    )
                )
        return sorted(
            nodes,
            key=lambda item: (
                item.calls_saved,
                item.cost_saved_usd,
                item.tokens_saved,
                item.latency_saved_ms,
            ),
            reverse=True,
        )[:5]

    def _is_savings_node(self, decision: ExecutionDecisionType, calls_saved: int) -> bool:
        if decision in {
            ExecutionDecisionType.CACHE_HIT,
            ExecutionDecisionType.SKIP,
            ExecutionDecisionType.GRAPH_REUSE,
        }:
            return True
        return calls_saved > 0

    def _recommendations(self, report: AttributionReport, reuse_rate: float) -> list[str]:
        recommendations: list[str] = []
        optimized = report.optimized
        if optimized.tokens_removed_by_projection > 0:
            recommendations.append(
                "Projection is removing repeated context; apply input_projection to similar downstream nodes."
            )
        if any(
            step.decision == ExecutionDecisionType.EXECUTE
            and step.raw_input_tokens >= 100
            and step.tokens_removed_by_projection == 0
            for step in optimized.per_step
        ):
            recommendations.append(
                "Some executed nodes still receive large unprojected inputs; consider input_projection."
            )
        if any(
            step.decision == ExecutionDecisionType.EXECUTE
            and step.raw_input_tokens == step.projected_input_tokens
            and step.raw_input_tokens >= 100
            for step in optimized.per_step
        ):
            recommendations.append(
                "Inspect high-token nodes for full dependency outputs; field slicing may reduce context."
            )
        if optimized.semantic_cache_hits:
            recommendations.append(
                "Semantic reuse is already avoiding similar work; keep thresholds conservative for safety."
            )
        if reuse_rate < 20.0:
            recommendations.append(
                "Low reuse observed; Helix saves most when inputs repeat or only partially change."
            )
        if not recommendations:
            recommendations.append("No obvious changes; current savings are primarily from skipped calls.")
        return self._dedupe(recommendations)

    def _dedupe(self, items: list[str]) -> list[str]:
        deduped: list[str] = []
        for item in items:
            if item not in deduped:
                deduped.append(item)
        return deduped
