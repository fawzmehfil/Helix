"""Run command."""

from __future__ import annotations

import click
from rich.table import Table

from helix.cli.commands._common import build_runner, console, parse_inputs
from helix.execution_optimizer.types import ExecutionDecision
from helix.workflow.types import StepResult
from helix.workflow import WorkflowParser


def _short_key(decision: ExecutionDecision | None) -> str:
    return decision.cache_key[:12] if decision and decision.cache_key else "-"


def _kv_value(step: StepResult, field: str) -> str:
    estimate = step.kv_estimate
    if estimate is None:
        return "0" if field == "prefix_overlap_tokens" else "0.00"
    value = getattr(estimate, field)
    if field == "prefix_overlap_tokens":
        return str(value)
    if field == "reused_fraction":
        return f"{value:.2%}"
    if field == "estimated_time_saved_ms":
        return f"{value:.1f}ms"
    if field == "estimated_cost_saved_usd":
        return f"${value:.6f}"
    return str(value)


@click.command("run")
@click.argument("workflow_path")
@click.option("--inputs", multiple=True, help="Template input as key=value.")
@click.option("--backend", default="fake", type=click.Choice(["fake", "openai", "anthropic"]))
@click.option("--verbose", is_flag=True, help="Show decision reasons.")
@click.option("--dry-run", is_flag=True, help="Show planned execution graph without executing it.")
def run_cmd(workflow_path: str, inputs: tuple[str, ...], backend: str, verbose: bool, dry_run: bool) -> None:
    """Execute an AI workload in optimized mode."""
    workflow = WorkflowParser().parse_file(workflow_path)
    if dry_run:
        table = Table(title=f"Execution graph {workflow.workflow_id}")
        table.add_column("Node")
        table.add_column("Type")
        table.add_column("Model")
        table.add_column("Depends on")
        for step in workflow.steps:
            table.add_row(step.step_id, step.step_type.value, step.model, ", ".join(step.depends_on))
        console.print(table)
        return
    runner = build_runner(backend, baseline=False)
    result = runner.run(workflow, parse_inputs(inputs))
    decisions = {
        decision.step_id: decision
        for decision in (result.optimization_plan.decisions if result.optimization_plan else [])
    }
    if verbose:
        table = Table(title=f"Helix execution: {workflow.workflow_id}")
        table.add_column("Field")
        for step in result.step_results:
            table.add_column(step.step_id)
        rows = [
            (
                "step_id",
                [step.step_id for step in result.step_results],
            ),
            (
                "decision",
                [step.decision.name for step in result.step_results],
            ),
            (
                "short cache key",
                [_short_key(decisions.get(step.step_id)) for step in result.step_results],
            ),
            (
                "input tokens",
                [str(step.input_tokens) for step in result.step_results],
            ),
            (
                "output tokens",
                [str(step.output_tokens) for step in result.step_results],
            ),
            (
                "latency",
                [f"{step.latency_ms:.0f}ms" for step in result.step_results],
            ),
            (
                "KV overlap tokens",
                [_kv_value(step, "prefix_overlap_tokens") for step in result.step_results],
            ),
            (
                "KV reused fraction",
                [_kv_value(step, "reused_fraction") for step in result.step_results],
            ),
            (
                "KV time saved",
                [_kv_value(step, "estimated_time_saved_ms") for step in result.step_results],
            ),
            (
                "KV cost saved",
                [_kv_value(step, "estimated_cost_saved_usd") for step in result.step_results],
            ),
            (
                "decision reason",
                [decisions[step.step_id].reason if step.step_id in decisions else "" for step in result.step_results],
            ),
        ]
        for label, values in rows:
            table.add_row(label, *values)
        console.print(table)
        return
    else:
        table = Table(title=f"Helix execution: {workflow.workflow_id}")
        table.add_column("Node")
        table.add_column("Decision")
        table.add_column("Input")
        table.add_column("Output")
        table.add_column("Latency")
        for step in result.step_results:
            table.add_row(
                step.step_id,
                step.decision.value,
                str(step.input_tokens),
                str(step.output_tokens),
                f"{step.latency_ms:.0f}ms",
            )
    console.print(table)
