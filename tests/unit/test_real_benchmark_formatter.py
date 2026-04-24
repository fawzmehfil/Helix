import datetime as dt

from helix.benchmark_engine import AttributionReport, BenchmarkResult, ReportFormatter


def _result(mode: str, latency: float, tokens: int, cost: float, calls: int) -> BenchmarkResult:
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
        raw_input_tokens=tokens,
        minimized_input_tokens=tokens,
        tokens_saved_by_minimization=0,
        optimization_overhead_tokens=0,
        net_token_change=0,
        semantic_cache_hits=0,
        avg_similarity_score=0.0,
        repair_attempts=0,
        repair_successes=0,
        per_step=[],
        timestamp=dt.datetime.now(dt.UTC),
    )


def test_real_benchmark_output_format():
    report = AttributionReport(
        baseline=_result("baseline", 2140, 1850, 0.021, 5),
        optimized=_result("optimized", 810, 710, 0.008, 2),
        latency_saved_ms=1330,
        latency_saved_pct=62.1,
        cost_saved_usd=0.013,
        cost_saved_pct=61.9,
        tokens_saved=1140,
        tokens_saved_pct=61.6,
        steps_reduced=3,
        calls_avoided=3,
        tokens_avoided=1140,
        steps_eliminated=0,
        partial_recomputation_steps=3,
        context_reuse_pct=61.6,
        kv_simulation_pct=0,
        graph_reuse_pct=0,
        step_reduction_pct=38.4,
    )

    output = ReportFormatter().format_real_benchmark(report)

    assert "=== HELIX EXECUTION REPORT ===" in output
    assert "Latency:" in output
    assert "Cost:" in output
    assert "Tokens:" in output
    assert "Calls:" in output
    assert "Calls avoided:" in output
    assert "Context minimization:" in output


def test_regression_warning_format_has_no_double_negative():
    report = AttributionReport(
        baseline=_result("baseline", 1000, 100, 0.001, 2),
        optimized=_result("optimized", 1200, 150, 0.002, 2),
        latency_saved_ms=-200,
        latency_saved_pct=-20,
        cost_saved_usd=-0.001,
        cost_saved_pct=-100,
        tokens_saved=-50,
        tokens_saved_pct=-50,
        steps_reduced=0,
        calls_avoided=0,
        tokens_avoided=-50,
        steps_eliminated=0,
        partial_recomputation_steps=0,
        context_reuse_pct=0,
        kv_simulation_pct=0,
        graph_reuse_pct=0,
        step_reduction_pct=0,
        warnings=["optimized tokens exceeded baseline by 50.0%"],
    )

    output = ReportFormatter().format_real_benchmark(report)

    assert "WARNING: Optimization regression detected" in output
    assert "--" not in output
