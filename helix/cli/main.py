"""Helix CLI entry point."""

from __future__ import annotations

import click

from helix.cli.commands.baseline import baseline_cmd
from helix.cli.commands.bench import bench_cmd
from helix.cli.commands.cache_cmd import cache_group
from helix.cli.commands.graph_cmd import graph_group
from helix.cli.commands.run import run_cmd


@click.group()
@click.version_option(version="0.1.0")
def cli() -> None:
    """Helix: computation-aware LLM agent optimizer."""


cli.add_command(run_cmd, name="run")
cli.add_command(baseline_cmd, name="baseline")
cli.add_command(bench_cmd, name="bench")
cli.add_command(cache_group, name="cache")
cli.add_command(graph_group, name="graph")

