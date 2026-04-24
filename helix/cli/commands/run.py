"""Run command."""

from __future__ import annotations

import click
from rich.table import Table

from helix.cli.commands._common import build_runner, console, parse_inputs
from helix.workflow import WorkflowParser


@click.command("run")
@click.argument("workflow_path")
@click.option("--inputs", multiple=True, help="Template input as key=value.")
@click.option("--backend", default="fake", type=click.Choice(["fake", "openai", "anthropic"]))
@click.option("--verbose", is_flag=True, help="Show decision reasons.")
@click.option("--dry-run", is_flag=True, help="Show planned workflow without execution.")
def run_cmd(workflow_path: str, inputs: tuple[str, ...], backend: str, verbose: bool, dry_run: bool) -> None:
    """Run a workflow in optimized mode."""
    workflow = WorkflowParser().parse_file(workflow_path)
    if dry_run:
        table = Table(title=f"Workflow {workflow.workflow_id}")
        table.add_column("Step")
        table.add_column("Type")
        table.add_column("Model")
        table.add_column("Depends on")
        for step in workflow.steps:
            table.add_row(step.step_id, step.step_type.value, step.model, ", ".join(step.depends_on))
        console.print(table)
        return
    runner = build_runner(backend, baseline=False)
    result = runner.run(workflow, parse_inputs(inputs))
    table = Table(title=f"Helix run: {workflow.workflow_id}")
    table.add_column("Step")
    table.add_column("Decision")
    table.add_column("Input")
    table.add_column("Output")
    table.add_column("Latency")
    for step in result.step_results:
        table.add_row(step.step_id, step.decision.value, str(step.input_tokens), str(step.output_tokens), f"{step.latency_ms:.0f}ms")
    console.print(table)
    if verbose and result.optimization_plan:
        for decision in result.optimization_plan.decisions:
            console.print(f"{decision.step_id}: {decision.reason}")

