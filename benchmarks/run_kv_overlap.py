"""Run the KV prefix-overlap demo benchmark."""

from __future__ import annotations

import os
import tempfile

from rich.console import Console
from rich.table import Table

from helix.cli.commands._common import build_runner
from helix.graph_engine import ComputationGraph
from helix.workflow import WorkflowParser


def _run(workflow_path: str, baseline: bool, state_dir: str):
    os.environ["HELIX_CACHE_PATH"] = os.path.join(state_dir, f"{'baseline' if baseline else 'optimized'}-cache.db")
    os.environ["HELIX_GRAPH_PATH"] = os.path.join(state_dir, f"{'baseline' if baseline else 'optimized'}-graph.db")
    os.environ["HELIX_RUNS_DIR"] = os.path.join(state_dir, "runs")
    runner = build_runner("fake", baseline=baseline)
    runner.optimizer.cache_store.clear()
    graph = runner.optimizer.graph
    if isinstance(graph, ComputationGraph):
        with graph._connect() as conn:
            conn.execute("DELETE FROM graph_nodes")
    workflow = WorkflowParser().parse_file(workflow_path)
    return runner.run(workflow, {})


def main() -> None:
    """Run baseline and optimized KV-overlap demo and print a comparison."""
    workflow_path = "workflows/demo_kv_overlap.yaml"
    state = tempfile.TemporaryDirectory(prefix="helix-kv-")
    baseline = _run(workflow_path, baseline=True, state_dir=state.name)
    optimized = _run(workflow_path, baseline=False, state_dir=state.name)

    table = Table(title="KV overlap demo")
    table.add_column("Mode")
    table.add_column("Latency", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("KV overlap tokens", justify="right")
    table.add_column("KV reused fraction", justify="right")
    table.add_column("Estimated KV time saved", justify="right")
    table.add_column("Estimated KV cost saved", justify="right")

    for label, result in [("baseline", baseline), ("optimized", optimized)]:
        overlap = sum(step.kv_estimate.prefix_overlap_tokens for step in result.step_results if step.kv_estimate)
        total_input = sum(step.input_tokens for step in result.step_results)
        time_saved = sum(step.kv_estimate.estimated_time_saved_ms for step in result.step_results if step.kv_estimate)
        cost_saved = sum(step.kv_estimate.estimated_cost_saved_usd for step in result.step_results if step.kv_estimate)
        reused = overlap / total_input if total_input else 0.0
        table.add_row(
            label,
            f"{result.total_latency_ms:.0f}ms",
            str(result.total_input_tokens + result.total_output_tokens),
            str(overlap),
            f"{reused:.2%}",
            f"{time_saved:.1f}ms",
            f"${cost_saved:.6f}",
        )

    Console().print(table)
    state.cleanup()


if __name__ == "__main__":
    main()
