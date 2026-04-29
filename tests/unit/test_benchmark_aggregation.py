import datetime as dt

from helix.benchmark_engine import AttributionReport, BenchmarkResult
from helix.benchmark_engine.aggregate import aggregate_reports, report_metrics


def _result(
    mode: str,
    latency: float,
    tokens: int,
    cost: float,
    calls: int,
    *,
    executed: int | None = None,
    cached: int = 0,
    graph_reused: int = 0,
    skipped: int = 0,
    raw_input_tokens: int | None = None,
    net_tokens_saved: int = 0,
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
        steps_executed=executed if executed is not None else calls,
        steps_cached=cached,
        steps_graph_reused=graph_reused,
        steps_skipped=skipped,
        calls=calls,
        raw_input_tokens=raw_input_tokens if raw_input_tokens is not None else tokens,
        projected_input_tokens=tokens,
        minimized_input_tokens=tokens - net_tokens_saved,
        tokens_removed_by_projection=0,
        optimization_overhead_tokens=0,
        net_tokens_saved_by_minimization=net_tokens_saved,
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
        per_step=[],
        timestamp=dt.datetime.now(dt.UTC),
    )


def _report(
    baseline_latency: float,
    optimized_latency: float,
    baseline_cost: float,
    optimized_cost: float,
    baseline_tokens: int,
    optimized_tokens: int,
    baseline_calls: int,
    optimized_calls: int,
) -> AttributionReport:
    baseline = _result(
        "baseline",
        baseline_latency,
        baseline_tokens,
        baseline_cost,
        baseline_calls,
        executed=4,
    )
    optimized = _result(
        "optimized",
        optimized_latency,
        optimized_tokens,
        optimized_cost,
        optimized_calls,
        executed=2,
        cached=1,
        graph_reused=1,
        skipped=0,
        raw_input_tokens=200,
        net_tokens_saved=50,
    )
    return AttributionReport(
        baseline=baseline,
        optimized=optimized,
        latency_saved_ms=baseline_latency - optimized_latency,
        latency_saved_pct=0.0,
        cost_saved_usd=baseline_cost - optimized_cost,
        cost_saved_pct=0.0,
        tokens_saved=baseline_tokens - optimized_tokens,
        tokens_saved_pct=0.0,
        steps_reduced=baseline.steps_executed - optimized.steps_executed,
        calls_avoided=baseline.calls - optimized.calls,
        tokens_avoided=baseline.total_tokens - optimized.total_tokens,
        steps_eliminated=optimized.steps_skipped,
        partial_recomputation_steps=optimized.steps_cached + optimized.steps_graph_reused,
        context_reuse_pct=0.0,
        kv_simulation_pct=0.0,
        graph_reuse_pct=0.0,
        step_reduction_pct=0.0,
    )


def test_aggregate_reports_calculates_avg_min_max_and_std_from_report_outputs():
    reports = [
        _report(1000, 500, 0.03, 0.01, 1000, 500, 4, 2),
        _report(1400, 700, 0.05, 0.03, 1400, 700, 6, 4),
    ]

    aggregate = aggregate_reports(reports)

    assert aggregate["avg"]["baseline_latency_ms"] == 1200
    assert aggregate["min"]["optimized_cost_usd"] == 0.01
    assert aggregate["max"]["baseline_tokens"] == 1400
    assert aggregate["std"]["optimized_latency_ms"] == 100
    assert aggregate["std"]["baseline_calls"] == 1
    assert aggregate["avg"]["reuse_rate_pct"] == 50
    assert aggregate["avg"]["recomputation_ratio_pct"] == 50
    assert aggregate["avg"]["context_reduction_pct"] == 25


def test_report_metrics_warns_without_crashing_on_failure_case_invariants():
    report = _report(1000, 900, 0.01, 0.02, 1000, 900, 2, 3)

    metrics = report_metrics(report)

    assert "optimized_calls exceeded baseline_calls" in metrics.warnings
    assert "optimized_cost exceeded baseline_cost" in metrics.warnings
