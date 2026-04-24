"""Graph commands."""

from __future__ import annotations

import click
from rich.table import Table

from helix.cli.commands._common import console
from helix.config import HelixConfig
from helix.graph_engine import ComputationGraph


@click.group("graph")
def graph_group() -> None:
    """Inspect the Helix computation graph."""


@graph_group.command("show")
@click.option("--dot", "show_dot", is_flag=True, help="Print Graphviz DOT.")
def graph_show(show_dot: bool) -> None:
    """Show graph nodes."""
    graph = ComputationGraph(HelixConfig.default().graph_db_path)
    if show_dot:
        console.print(graph.export_dot())
        return
    table = Table(title="Helix graph")
    table.add_column("Run")
    table.add_column("Step")
    table.add_column("Model")
    table.add_column("Input")
    for run_id in graph.list_runs():
        for node in graph.get_run_nodes(run_id):
            table.add_row(run_id[:8], node.step_id, node.model_id, node.input_hash[:12])
    console.print(table)

