"""Bench command."""

from __future__ import annotations

import json
import os
import tempfile

import click

from helix.benchmark_engine import BenchmarkRunner, ReportFormatter
from helix.cli.commands._common import build_runner, console, parse_inputs
from helix.config import HelixConfig
from helix.exceptions import LLMClientError
from helix.workflow import WorkflowParser


def _select_real_backend(requested: str) -> str | None:
    if requested in {"openai", "anthropic"}:
        return requested
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return None


def _metadata_inputs(workflow, key: str) -> dict[str, str]:
    raw = workflow.metadata.get(key, {})
    return {str(k): str(v) for k, v in raw.items()} if isinstance(raw, dict) else {}


def _force_workflow_model(workflow, model: str) -> None:
    workflow.default_model = model
    for step in workflow.steps:
        step.model = model


def _step_json(step) -> dict:
    return {
        "step_id": step.step_id,
        "decision": step.decision.value,
        "input_tokens": step.input_tokens,
        "output_tokens": step.output_tokens,
        "total_tokens": step.input_tokens + step.output_tokens,
        "raw_input_tokens": step.raw_input_tokens,
        "projected_input_tokens": step.projected_input_tokens,
        "minimized_input_tokens": step.minimized_input_tokens,
        "tokens_removed_by_projection": step.tokens_removed_by_projection,
        "optimization_overhead_tokens": step.optimization_overhead_tokens,
        "net_tokens_saved_by_minimization": step.net_tokens_saved_by_minimization,
        "minimization_effective": step.minimization_effective,
        "tokens_trimmed_by_budget": step.tokens_trimmed_by_budget,
        "budget_applied": step.budget_applied,
        "minimization_warnings": step.minimization_warnings,
        "cache_hit": step.cache_hit,
        "semantic_cache_hit": step.semantic_cache_hit,
        "semantic_reuse_applied": step.semantic_reuse_applied,
        "similarity_score": step.similarity_score,
        "graph_reuse": step.graph_reuse,
        "latency_ms": step.latency_ms,
        "cost_usd": step.estimated_cost_usd,
        "model": step.model,
        "call_count": step.call_count,
        "repair_attempted": step.repair_attempted,
        "repair_successful": step.repair_successful,
        "schema_validation_failed": step.schema_validation_failed,
        "structured_output_failed": step.structured_output_failed,
    }


def _result_json(result) -> dict:
    return {
        "run_id": result.run_id,
        "workflow_id": result.workflow_id,
        "mode": result.mode,
        "total_latency_ms": result.total_latency_ms,
        "total_input_tokens": result.total_input_tokens,
        "total_output_tokens": result.total_output_tokens,
        "total_tokens": result.total_tokens,
        "estimated_cost_usd": result.estimated_cost_usd,
        "calls": result.calls,
        "steps_executed": result.steps_executed,
        "steps_cached": result.steps_cached,
        "steps_graph_reused": result.steps_graph_reused,
        "steps_skipped": result.steps_skipped,
        "context_minimization": {
            "raw_input_tokens": result.raw_input_tokens,
            "projected_input_tokens": result.projected_input_tokens,
            "minimized_input_tokens": result.minimized_input_tokens,
            "tokens_removed_by_projection": result.tokens_removed_by_projection,
            "optimization_overhead_tokens": result.optimization_overhead_tokens,
            "net_tokens_saved_by_minimization": result.net_tokens_saved_by_minimization,
            "minimization_effective": result.net_tokens_saved_by_minimization > 0,
            "tokens_trimmed_by_budget": result.tokens_trimmed_by_budget,
            "budget_applied_steps": result.budget_applied_steps,
            "warnings": result.minimization_warnings,
        },
        "semantic_reuse": {
            "semantic_cache_hits": result.semantic_cache_hits,
            "avg_similarity_score": result.avg_similarity_score,
        },
        "structured_output": {
            "repair_attempts": result.repair_attempts,
            "repair_successes": result.repair_successes,
            "schema_validation_failures": result.schema_validation_failures,
        },
        "per_step": [_step_json(step) for step in result.per_step],
    }


def _write_json_report(path: str, report, backend: str, model: str) -> None:
    payload = {
        "workflow_id": report.baseline.workflow_id,
        "backend": backend,
        "model": model,
        "timestamp": report.optimized.timestamp.isoformat(),
        "baseline": _result_json(report.baseline),
        "optimized": _result_json(report.optimized),
        "context_minimization": {
            "raw_input_tokens": report.optimized.raw_input_tokens,
            "projected_input_tokens": report.optimized.projected_input_tokens,
            "minimized_input_tokens": report.optimized.minimized_input_tokens,
            "tokens_removed_by_projection": report.optimized.tokens_removed_by_projection,
            "optimization_overhead_tokens": report.optimized.optimization_overhead_tokens,
            "net_tokens_saved_by_minimization": report.optimized.net_tokens_saved_by_minimization,
            "minimization_effective": report.optimized.net_tokens_saved_by_minimization > 0,
            "tokens_trimmed_by_budget": report.optimized.tokens_trimmed_by_budget,
            "warnings": report.optimized.minimization_warnings,
        },
        "semantic_reuse": {
            "semantic_cache_hits": report.optimized.semantic_cache_hits,
            "avg_similarity_score": report.optimized.avg_similarity_score,
            "semantic_calls_avoided": report.semantic_calls_avoided,
            "semantic_tokens_avoided": report.semantic_tokens_avoided,
        },
        "structured_output": {
            "repair_attempts": report.optimized.repair_attempts,
            "repair_successes": report.optimized.repair_successes,
            "schema_validation_failures": report.optimized.schema_validation_failures,
        },
        "warnings": report.warnings,
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


@click.command("bench")
@click.argument("workflow_path")
@click.option("--inputs", multiple=True, help="Template input as key=value.")
@click.option("--backend", default="fake", type=click.Choice(["fake", "openai", "anthropic"]))
@click.option("--verbose", is_flag=True, help="Show per-step decisions.")
@click.option("--real", is_flag=True, help="Use real provider APIs instead of the fake backend.")
@click.option("--isolated", is_flag=True, help="Use temporary cache and graph storage for this benchmark.")
@click.option("--cache-path", default=None, help="Cache database path for this benchmark.")
@click.option("--graph-path", default=None, help="Graph database path for this benchmark.")
@click.option("--json-out", default=None, help="Write benchmark results to a JSON artifact.")
def bench_cmd(
    workflow_path: str,
    inputs: tuple[str, ...],
    backend: str,
    verbose: bool,
    real: bool,
    isolated: bool,
    cache_path: str | None,
    graph_path: str | None,
    json_out: str | None,
) -> None:
    """Run baseline vs optimized benchmark."""
    workflow = WorkflowParser().parse_file(workflow_path)
    parsed_inputs = parse_inputs(inputs)
    temp_state = None
    try:
        if real:
            selected_backend = _select_real_backend(backend)
            if selected_backend is None:
                console.print(
                    "Real benchmark skipped: set OPENAI_API_KEY or ANTHROPIC_API_KEY, "
                    "or pass --backend openai/anthropic."
                )
                return
            model = "gpt-4o-mini" if selected_backend == "openai" else "claude-3-haiku-20240307"
            _force_workflow_model(workflow, model)
            if isolated or (cache_path is None and graph_path is None):
                temp_state = tempfile.TemporaryDirectory(prefix="helix-real-bench-")
            root = temp_state.name if temp_state else None
            baseline_cache = cache_path or (os.path.join(root, "baseline-cache.db") if root else None)
            baseline_graph = graph_path or (os.path.join(root, "baseline-graph.db") if root else None)
            optimized_cache = cache_path or (os.path.join(root, "optimized-cache.db") if root else None)
            optimized_graph = graph_path or (os.path.join(root, "optimized-graph.db") if root else None)
            baseline = build_runner(
                selected_backend,
                baseline=True,
                cache_path=baseline_cache,
                graph_path=baseline_graph,
                model=model,
                require_available=True,
            )
            optimized = build_runner(
                selected_backend,
                baseline=False,
                cache_path=optimized_cache,
                graph_path=optimized_graph,
                model=model,
                require_available=True,
            )
            measured_inputs = parsed_inputs or _metadata_inputs(workflow, "measured_inputs")
            warmup_inputs = _metadata_inputs(workflow, "warmup_inputs") or measured_inputs
            report = BenchmarkRunner(
                baseline,
                optimized,
                HelixConfig.default().cost_table,
            ).run_real_comparison(workflow, measured_inputs, warmup_inputs)
            console.print(ReportFormatter().format_real_benchmark(report))
            if json_out:
                _write_json_report(json_out, report, selected_backend, model)
        else:
            baseline = build_runner(backend, baseline=True, cache_path=cache_path, graph_path=graph_path)
            optimized = build_runner(backend, baseline=False, cache_path=cache_path, graph_path=graph_path)
            report = BenchmarkRunner(baseline, optimized, HelixConfig.default().cost_table).run_comparison(
                workflow, parsed_inputs
            )
            console.print(ReportFormatter().format_attribution(report))
            if json_out:
                model = report.baseline.per_step[0].model if report.baseline.per_step else backend
                _write_json_report(json_out, report, backend, model)
    except LLMClientError as exc:
        console.print(str(exc))
        return
    finally:
        if temp_state is not None:
            temp_state.cleanup()
    if verbose:
        for step in report.optimized.per_step:
            console.print(f"{step.step_id}: {step.decision.value}")
