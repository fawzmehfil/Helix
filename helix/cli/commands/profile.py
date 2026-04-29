"""Savings profile command."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict

import click

from helix.benchmark_engine import BenchmarkRunner
from helix.cli.commands._common import build_runner, console, parse_inputs
from helix.config import HelixConfig
from helix.exceptions import LLMClientError
from helix.profiler import SavingsProfileFormatter, SavingsProfiler
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


@click.command("profile")
@click.argument("workflow_path")
@click.option("--inputs", multiple=True, help="Template input as key=value.")
@click.option("--backend", default="fake", type=click.Choice(["fake", "openai", "anthropic"]))
@click.option("--real", is_flag=True, help="Use real provider APIs instead of the fake backend.")
@click.option("--isolated", is_flag=True, help="Use temporary cache and graph storage for this profile.")
@click.option("--cache-path", default=None, help="Cache database path for this profile.")
@click.option("--graph-path", default=None, help="Graph database path for this profile.")
@click.option("--parallel", is_flag=True, help="Profile optimized execution with DAG-level parallel execution.")
@click.option("--json-out", default=None, help="Write savings profile to a JSON artifact.")
@click.option(
    "--semantic-review",
    default=None,
    type=click.Choice(["auto_accept", "auto_reject", "interactive"]),
    help="Override semantic reuse review mode.",
)
def profile_cmd(
    workflow_path: str,
    inputs: tuple[str, ...],
    backend: str,
    real: bool,
    isolated: bool,
    cache_path: str | None,
    graph_path: str | None,
    parallel: bool,
    json_out: str | None,
    semantic_review: str | None,
) -> None:
    """Explain where Helix eliminates redundant LLM work."""
    workflow = WorkflowParser().parse_file(workflow_path)
    parsed_inputs = parse_inputs(inputs)
    temp_state = None
    try:
        if real:
            selected_backend = _select_real_backend(backend)
            if selected_backend is None:
                console.print(
                    "Real profile skipped: set OPENAI_API_KEY or ANTHROPIC_API_KEY, "
                    "or pass --backend openai/anthropic."
                )
                return
            model = "gpt-4o-mini" if selected_backend == "openai" else "claude-3-haiku-20240307"
            _force_workflow_model(workflow, model)
            if isolated or (cache_path is None and graph_path is None):
                temp_state = tempfile.TemporaryDirectory(prefix="helix-real-profile-")
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
            if semantic_review:
                optimized.optimizer.semantic_review_mode = semantic_review
            measured_inputs = parsed_inputs or _metadata_inputs(workflow, "measured_inputs")
            warmup_inputs = _metadata_inputs(workflow, "warmup_inputs") or measured_inputs
            runner = BenchmarkRunner(baseline, optimized, HelixConfig.default().cost_table)
            report = (
                runner.run_parallel_comparison(workflow, measured_inputs)
                if parallel
                else runner.run_real_comparison(workflow, measured_inputs, warmup_inputs)
            )
        else:
            baseline = build_runner(backend, baseline=True, cache_path=cache_path, graph_path=graph_path)
            optimized = build_runner(backend, baseline=False, cache_path=cache_path, graph_path=graph_path)
            if semantic_review:
                optimized.optimizer.semantic_review_mode = semantic_review
            runner = BenchmarkRunner(baseline, optimized, HelixConfig.default().cost_table)
            report = (
                runner.run_parallel_comparison(workflow, parsed_inputs)
                if parallel
                else runner.run_comparison(workflow, parsed_inputs)
            )
        profile = SavingsProfiler().analyze(report)
        console.print(SavingsProfileFormatter().format(profile))
        if json_out:
            with open(json_out, "w", encoding="utf-8") as handle:
                json.dump(asdict(profile), handle, indent=2)
    except LLMClientError as exc:
        console.print(str(exc))
        return
    finally:
        if temp_state is not None:
            temp_state.cleanup()
