"""Bench command."""

from __future__ import annotations

import click

from helix.benchmark_engine import BenchmarkRunner, ReportFormatter
from helix.cli.commands._common import build_runner, console, parse_inputs
from helix.config import HelixConfig
from helix.workflow import WorkflowParser


@click.command("bench")
@click.argument("workflow_path")
@click.option("--inputs", multiple=True, help="Template input as key=value.")
@click.option("--backend", default="fake", type=click.Choice(["fake", "openai", "anthropic"]))
@click.option("--verbose", is_flag=True, help="Show per-step decisions.")
def bench_cmd(workflow_path: str, inputs: tuple[str, ...], backend: str, verbose: bool) -> None:
    """Run baseline vs optimized benchmark."""
    workflow = WorkflowParser().parse_file(workflow_path)
    baseline = build_runner(backend, baseline=True)
    optimized = build_runner(backend, baseline=False)
    report = BenchmarkRunner(baseline, optimized, HelixConfig.default().cost_table).run_comparison(
        workflow, parse_inputs(inputs)
    )
    console.print(ReportFormatter().format_attribution(report))
    if verbose:
        for step in report.optimized.per_step:
            console.print(f"{step.step_id}: {step.decision.value}")

