"""Run the partial-change fake benchmark."""

from __future__ import annotations

import os
import tempfile

from rich.console import Console
from rich.table import Table

from helix.cli.commands._common import build_runner
from helix.graph_engine import ComputationGraph
from helix.workflow import WorkflowParser


INPUTS = [
    ("1", "v1", "Helix records deterministic context hashes and reuses safe LLM computations."),
    ("2", "v1", "Helix records deterministic context hashes and reuses safe LLM computations."),
    ("3", "v2", "Helix records deterministic context hashes, estimates KV overlap, and reuses safe LLM computations."),
    ("4", "v2", "Helix records deterministic context hashes, estimates KV overlap, and reuses safe LLM computations."),
]


def main() -> None:
    """Run cold, repeated, changed, and repeated-changed inputs."""
    state_dir = tempfile.TemporaryDirectory(prefix="helix-partial-")
    os.environ["HELIX_CACHE_PATH"] = os.path.join(state_dir.name, "cache.db")
    os.environ["HELIX_GRAPH_PATH"] = os.path.join(state_dir.name, "graph.db")
    os.environ["HELIX_RUNS_DIR"] = os.path.join(state_dir.name, "runs")
    workflow = WorkflowParser().parse_file("workflows/demo_partial_change.yaml")
    runner = build_runner("fake", baseline=False)
    runner.optimizer.cache_store.clear()
    graph = runner.optimizer.graph
    if isinstance(graph, ComputationGraph):
        with graph._connect() as conn:
            conn.execute("DELETE FROM graph_nodes")

    table = Table(title="Partial-change demo")
    table.add_column("Run", justify="right")
    table.add_column("Input version")
    table.add_column("Steps executed", justify="right")
    table.add_column("Cache hits", justify="right")
    table.add_column("Graph reuse", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Latency", justify="right")

    for run_number, version, document in INPUTS:
        result = runner.run(workflow, {"document": document})
        table.add_row(
            run_number,
            version,
            str(sum(1 for step in result.step_results if step.decision.value == "execute")),
            str(sum(1 for step in result.step_results if step.cache_hit)),
            str(sum(1 for step in result.step_results if step.graph_reuse)),
            str(result.total_input_tokens + result.total_output_tokens),
            f"{result.total_latency_ms:.0f}ms",
        )

    Console().print(table)
    state_dir.cleanup()


if __name__ == "__main__":
    main()
