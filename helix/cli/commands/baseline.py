"""Baseline command."""

from __future__ import annotations

import click
from rich.table import Table

from helix.cli.commands._common import build_runner, console, parse_inputs
from helix.workflow import WorkflowParser


@click.command("baseline")
@click.argument("workflow_path")
@click.option("--inputs", multiple=True, help="Template input as key=value.")
@click.option("--backend", default="fake", type=click.Choice(["fake", "openai", "anthropic"]))
def baseline_cmd(workflow_path: str, inputs: tuple[str, ...], backend: str) -> None:
    """Execute an AI workload without optimizations."""
    workflow = WorkflowParser().parse_file(workflow_path)
    runner = build_runner(backend, baseline=True)
    result = runner.run(workflow, parse_inputs(inputs))
    table = Table(title=f"Helix baseline: {workflow.workflow_id}")
    table.add_column("Node")
    table.add_column("Decision")
    table.add_column("Input")
    table.add_column("Output")
    table.add_column("Latency")
    for step in result.step_results:
        table.add_row(step.step_id, step.decision.value, str(step.input_tokens), str(step.output_tokens), f"{step.latency_ms:.0f}ms")
    console.print(table)
