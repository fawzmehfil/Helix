import datetime as dt

from helix.benchmark_engine import AttributionReport, BenchmarkResult
from helix.benchmark_engine.runner import BenchmarkRunner
from helix.cli.commands._common import build_runner
from helix.execution_optimizer.types import ExecutionDecisionType
from helix.workflow.types import StepResult
from helix.workflow import WorkflowParser


def _step(step_id: str, net: int) -> StepResult:
    raw = 100
    minimized = raw - net
    return StepResult(
        step_id=step_id,
        decision=ExecutionDecisionType.EXECUTE,
        response={"content": "{}"},
        input_tokens=10,
        output_tokens=5,
        latency_ms=10.0,
        kv_estimate=None,
        cache_hit=False,
        graph_reuse=False,
        raw_input_tokens=raw,
        projected_input_tokens=minimized,
        minimized_input_tokens=minimized,
        tokens_removed_by_projection=max(net, 0),
        net_tokens_saved_by_minimization=net,
        minimization_warnings=["Context minimization regression: optimized prompt larger than raw prompt"]
        if net < 0
        else [],
    )


def _result(
    mode: str,
    tokens: int,
    cost: float,
    latency: float,
    calls: int,
    net_min: int,
    steps: list[StepResult],
) -> BenchmarkResult:
    return BenchmarkResult(
        run_id=f"{mode}-run",
        workflow_id="w",
        mode=mode,
        total_latency_ms=latency,
        total_input_tokens=tokens,
        total_output_tokens=0,
        total_tokens=tokens,
        estimated_cost_usd=cost,
        steps_executed=calls,
        steps_cached=0,
        steps_graph_reused=0,
        steps_skipped=0,
        calls=calls,
        raw_input_tokens=sum(step.raw_input_tokens for step in steps),
        projected_input_tokens=sum(step.projected_input_tokens for step in steps),
        minimized_input_tokens=sum(step.minimized_input_tokens for step in steps),
        tokens_removed_by_projection=sum(step.tokens_removed_by_projection for step in steps),
        optimization_overhead_tokens=0,
        net_tokens_saved_by_minimization=net_min,
        minimization_effective_steps=sum(1 for step in steps if step.net_tokens_saved_by_minimization > 0),
        tokens_trimmed_by_budget=0,
        budget_applied_steps=0,
        minimization_warnings=[
            warning for step in steps for warning in step.minimization_warnings
        ],
        tokens_saved_by_minimization=max(net_min, 0),
        net_token_change=-net_min,
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


def _report(baseline: BenchmarkResult, optimized: BenchmarkResult) -> AttributionReport:
    runner = BenchmarkRunner(build_runner("fake", baseline=True), build_runner("fake", baseline=False), {})
    return runner._build_report(baseline, optimized)


def test_cached_step_with_prompt_overhead_does_not_emit_minimization_warning():
    workflow = WorkflowParser().parse_yaml(
        """
workflow_id: cached_warning_test
name: Cached Warning Test
steps:
  - step_id: s
    step_type: llm_call
    model: fake
    compact: true
    messages:
      - role: user
        content: "tiny"
"""
    )
    optimized = build_runner("fake", baseline=False)
    optimized.optimizer.cache_store.clear()
    optimized.run(workflow, {})
    second = optimized.run(workflow, {})

    assert second.step_results[0].cache_hit is True
    assert second.step_results[0].minimization_warnings == []


def test_executed_prompt_regression_still_warns():
    workflow = WorkflowParser().parse_yaml(
        """
workflow_id: executed_warning_test
name: Executed Warning Test
steps:
  - step_id: s
    step_type: llm_call
    model: fake
    compact: true
    messages:
      - role: user
        content: "tiny"
"""
    )
    optimized = build_runner("fake", baseline=False)
    optimized.optimizer.cache_store.clear()

    result = optimized.run(workflow, {})

    assert "Context minimization regression: optimized prompt larger than raw prompt" in (
        result.step_results[0].minimization_warnings
    )


def test_positive_aggregate_minimization_with_negative_step_is_note_not_global_warning():
    baseline = _result("baseline", 200, 0.002, 1000, 2, 0, [_step("a", 0), _step("b", 0)])
    optimized = _result("optimized", 100, 0.001, 500, 2, 60, [_step("a", 100), _step("b", -40)])

    report = _report(baseline, optimized)

    assert report.warnings == []
    assert report.notes == ["b: context minimization net negative (-40 tokens)"]


def test_negative_aggregate_minimization_is_global_warning():
    baseline = _result("baseline", 200, 0.002, 1000, 2, 0, [_step("a", 0)])
    optimized = _result("optimized", 100, 0.001, 500, 2, -10, [_step("a", -10)])

    report = _report(baseline, optimized)

    assert "context minimization net negative (-10 tokens)" in report.warnings


def test_true_cost_and_token_regression_remains_global_warning():
    baseline = _result("baseline", 100, 0.001, 1000, 2, 20, [_step("a", 20)])
    optimized = _result("optimized", 150, 0.002, 900, 2, 20, [_step("a", 20)])

    report = _report(baseline, optimized)

    assert "optimized tokens exceeded baseline by 50.0%" in report.warnings
    assert "optimized cost exceeded baseline by 100.0%" in report.warnings
