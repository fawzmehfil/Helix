"""Savings profile formatting."""

from __future__ import annotations

from io import StringIO

from rich.console import Console
from rich.table import Table

from helix.profiler.types import SavingsProfile


class SavingsProfileFormatter:
    """Format SavingsProfile objects for the terminal."""

    def format(self, profile: SavingsProfile) -> str:
        """Return a human-readable savings profile."""
        out = StringIO()
        console = Console(file=out, force_terminal=False, width=100)
        console.print("Helix Savings Profile")
        console.print()
        console.print(f"Workflow: {profile.workflow_id}")
        console.print()
        console.print("Baseline:")
        console.print(f"- Calls:   {profile.baseline_calls}")
        console.print(f"- Tokens:  {profile.baseline_tokens}")
        console.print(f"- Cost:    ${profile.baseline_cost_usd:.6f}")
        console.print(f"- Latency: {profile.baseline_latency_ms / 1000.0:.2f}s")
        console.print()
        console.print("Optimized:")
        console.print(f"- Calls:   {profile.optimized_calls}")
        console.print(f"- Tokens:  {profile.optimized_tokens}")
        console.print(f"- Cost:    ${profile.optimized_cost_usd:.6f}")
        console.print(f"- Latency: {profile.optimized_latency_ms / 1000.0:.2f}s")
        console.print()
        console.print("Savings:")
        console.print(f"- Calls avoided:       {profile.calls_avoided}")
        console.print(
            f"- Cost saved:          ${profile.cost_saved_usd:.6f} "
            f"({profile.cost_saved_pct:.1f}%)"
        )
        console.print(
            f"- Tokens saved:        {profile.tokens_saved} "
            f"({profile.tokens_saved_pct:.1f}%)"
        )
        console.print(
            f"- Latency reduction:   {profile.latency_saved_ms / 1000.0:.2f}s "
            f"({profile.latency_saved_pct:.1f}%)"
        )
        console.print()
        console.print("Reuse Breakdown:")
        console.print(f"- exact cache hits:       {profile.exact_cache_hits}")
        console.print(f"- semantic hits:          {profile.semantic_hits}")
        console.print(f"- nodes executed:         {profile.nodes_executed}")
        console.print(f"- nodes skipped/reused:   {profile.nodes_reused}")
        console.print(f"- reuse rate:             {profile.reuse_rate_pct:.1f}%")
        console.print(f"- recomputation ratio:    {profile.recomputation_ratio_pct:.1f}%")
        console.print()
        self._top_nodes(console, profile)
        console.print()
        console.print("Context Minimization:")
        console.print(f"- raw tokens:        {profile.raw_input_tokens}")
        console.print(f"- minimized tokens:  {profile.minimized_input_tokens}")
        console.print(f"- reduction:         {profile.context_reduction_pct:.1f}%")
        console.print()
        console.print("Recommendations:")
        for recommendation in profile.recommendations:
            console.print(f"- {recommendation}")
        if profile.warnings:
            console.print()
            console.print("Warnings:")
            for warning in profile.warnings:
                console.print(f"- {warning}")
        if profile.notes:
            console.print()
            console.print("Notes:")
            for note in profile.notes:
                console.print(f"- {note}")
        return out.getvalue()

    def _top_nodes(self, console: Console, profile: SavingsProfile) -> None:
        console.print("Top Savings Nodes:")
        if not profile.top_savings_nodes:
            console.print("- none")
            return
        table = Table(show_header=True, box=None)
        table.add_column("node")
        table.add_column("decision")
        table.add_column("calls", justify="right")
        table.add_column("tokens", justify="right")
        table.add_column("cost", justify="right")
        table.add_column("latency", justify="right")
        for node in profile.top_savings_nodes:
            table.add_row(
                node.step_id,
                node.decision,
                str(node.calls_saved),
                str(node.tokens_saved),
                f"${node.cost_saved_usd:.6f}",
                f"{node.latency_saved_ms / 1000.0:.2f}s",
            )
        console.print(table)
