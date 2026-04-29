"""Aggregate repeated benchmark reports."""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import fmean

from helix.benchmark_engine.types import AttributionReport


@dataclass(frozen=True)
class ReportMetrics:
    """Metrics extracted from one AttributionReport."""

    values: dict[str, float]
    warnings: list[str]


def report_metrics(report: AttributionReport) -> ReportMetrics:
    """Return repeatable reporting metrics from an existing AttributionReport."""
    steps_skipped = (
        report.optimized.steps_cached
        + report.optimized.steps_graph_reused
        + report.optimized.steps_skipped
    )
    total_nodes = max(
        report.optimized.steps_executed + steps_skipped,
        report.baseline.steps_executed,
        1,
    )
    reuse_rate = steps_skipped / total_nodes * 100.0
    recomputation_ratio = report.optimized.steps_executed / total_nodes * 100.0
    context_reduction = (
        report.optimized.net_tokens_saved_by_minimization
        / report.optimized.raw_input_tokens
        * 100.0
        if report.optimized.raw_input_tokens
        else 0.0
    )
    values = {
        "baseline_latency_ms": float(report.baseline.total_latency_ms),
        "optimized_latency_ms": float(report.optimized.total_latency_ms),
        "baseline_cost_usd": float(report.baseline.estimated_cost_usd),
        "optimized_cost_usd": float(report.optimized.estimated_cost_usd),
        "baseline_tokens": float(report.baseline.total_tokens),
        "optimized_tokens": float(report.optimized.total_tokens),
        "baseline_calls": float(report.baseline.calls),
        "optimized_calls": float(report.optimized.calls),
        "reuse_rate_pct": reuse_rate,
        "recomputation_ratio_pct": recomputation_ratio,
        "context_reduction_pct": max(context_reduction, 0.0),
    }
    warnings = list(report.warnings)
    if report.optimized.calls > report.baseline.calls:
        warnings.append("optimized_calls exceeded baseline_calls")
    if report.optimized.estimated_cost_usd > report.baseline.estimated_cost_usd:
        warnings.append("optimized_cost exceeded baseline_cost")
    if not math.isclose(reuse_rate + recomputation_ratio, 100.0, abs_tol=1.0):
        warnings.append("reuse_rate plus recomputation_ratio did not sum to approximately 100%")
    return ReportMetrics(values=values, warnings=_dedupe(warnings))


def aggregate_reports(reports: list[AttributionReport]) -> dict[str, dict[str, float]]:
    """Aggregate metrics from repeated benchmark_engine reports."""
    if not reports:
        raise ValueError("at least one report is required")
    snapshots = [report_metrics(report).values for report in reports]
    keys = snapshots[0].keys()
    aggregate: dict[str, dict[str, float]] = {
        "avg": {},
        "std": {},
        "min": {},
        "max": {},
    }
    for key in keys:
        values = [snapshot[key] for snapshot in snapshots]
        avg = fmean(values)
        aggregate["avg"][key] = avg
        aggregate["std"][key] = _population_std(values, avg)
        aggregate["min"][key] = min(values)
        aggregate["max"][key] = max(values)
    return aggregate


def aggregate_warnings(reports: list[AttributionReport]) -> list[str]:
    """Collect validation warnings from repeated benchmark reports."""
    warnings: list[str] = []
    for report in reports:
        warnings.extend(report_metrics(report).warnings)
    return _dedupe(warnings)


def _population_std(values: list[float], avg: float) -> float:
    if len(values) == 1:
        return 0.0
    variance = fmean([(value - avg) ** 2 for value in values])
    return math.sqrt(variance)


def _dedupe(warnings: list[str]) -> list[str]:
    deduped: list[str] = []
    for warning in warnings:
        if warning not in deduped:
            deduped.append(warning)
    return deduped
