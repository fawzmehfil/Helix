import datetime as dt

from helix.benchmark_engine.types import AttributionReport, BenchmarkResult
from helix.execution_optimizer.types import ExecutionDecisionType
from helix.profiler import SavingsProfiler
from helix.workflow.types import StepResult


def _step(step_id: str, decision: ExecutionDecisionType, tokens: int, latency: float) -> StepResult:
    return StepResult(
        step_id=step_id,
        decision=decision,
        response={},
        input_tokens=tokens,
        output_tokens=0,
        latency_ms=latency,
        kv_estimate=None,
        cache_hit=decision == ExecutionDecisionType.CACHE_HIT,
        graph_reuse=decision == ExecutionDecisionType.GRAPH_REUSE,
        call_count=0 if decision == ExecutionDecisionType.CACHE_HIT else 1,
    )


def _result(mode: str, steps: list[StepResult]) -> BenchmarkResult:
    return BenchmarkResult(
        run_id=f"{mode}-run",
        workflow_id="profile_test",
        mode=mode,
        total_latency_ms=sum(step.latency_ms for step in steps),
        total_input_tokens=sum(step.input_tokens for step in steps),
        total_output_tokens=0,
        total_tokens=sum(step.input_tokens for step in steps),
        estimated_cost_usd=0.0,
        steps_executed=sum(1 for step in steps if step.decision == ExecutionDecisionType.EXECUTE),
        steps_cached=sum(1 for step in steps if step.decision == ExecutionDecisionType.CACHE_HIT),
        steps_graph_reused=0,
        steps_skipped=0,
        calls=sum(step.call_count for step in steps),
        raw_input_tokens=sum(step.input_tokens for step in steps),
        projected_input_tokens=sum(step.input_tokens for step in steps),
        minimized_input_tokens=sum(step.input_tokens for step in steps),
        tokens_removed_by_projection=0,
        optimization_overhead_tokens=0,
        net_tokens_saved_by_minimization=0,
        minimization_effective_steps=0,
        tokens_trimmed_by_budget=0,
        budget_applied_steps=0,
        minimization_warnings=[],
        tokens_saved_by_minimization=0,
        net_token_change=0,
        semantic_cache_hits=0,
        semantic_reuse_accepted=0,
        semantic_reuse_rejected=0,
        avg_similarity_score=0.0,
        embedding_latency_ms=0.0,
        embedding_calls=0,
        repair_attempts=0,
        repair_successes=0,
        schema_validation_failures=0,
        per_step=steps,
        timestamp=dt.datetime.now(dt.UTC),
    )


def test_top_savings_nodes_excludes_executed_incidental_deltas():
    baseline = _result(
        "baseline",
        [
            _step("stable", ExecutionDecisionType.EXECUTE, 100, 100),
            _step("changed", ExecutionDecisionType.EXECUTE, 100, 100),
        ],
    )
    optimized = _result(
        "optimized",
        [
            _step("stable", ExecutionDecisionType.CACHE_HIT, 0, 0),
            _step("changed", ExecutionDecisionType.EXECUTE, 50, 10),
        ],
    )
    report = AttributionReport(
        baseline=baseline,
        optimized=optimized,
        latency_saved_ms=190,
        latency_saved_pct=95,
        cost_saved_usd=0,
        cost_saved_pct=0,
        tokens_saved=150,
        tokens_saved_pct=75,
        steps_reduced=1,
        calls_avoided=1,
        tokens_avoided=100,
        steps_eliminated=0,
        partial_recomputation_steps=1,
        context_reuse_pct=50,
        kv_simulation_pct=0,
        graph_reuse_pct=0,
        step_reduction_pct=50,
    )

    profile = SavingsProfiler().analyze(report)

    assert [node.step_id for node in profile.top_savings_nodes] == ["stable"]
