"""Rich benchmark report formatting."""

from __future__ import annotations

from io import StringIO

from rich.console import Console
from rich.table import Table

from helix.benchmark_engine.types import AttributionReport, BenchmarkResult
from helix.workflow.types import RunResult


class ReportFormatter:
    """Format run and benchmark reports for the terminal."""

    def _savings(self, pct: float, cost: bool = False) -> str:
        if cost and pct == 0:
            return "N/A"
        return f"-{pct:.1f}%"

    def format_attribution(self, report: AttributionReport) -> str:
        """Returns the terminal report string."""
        out = StringIO()
        console = Console(file=out, force_terminal=False, width=100)
        console.print("╔══════════════════════════════════════════════════════╗")
        console.print("║           Helix Benchmark Results                    ║")
        console.print("╚══════════════════════════════════════════════════════╝")
        console.print()
        console.print(f"Workflow:      {report.baseline.workflow_id}")
        console.print("Backend:       fake / fake")
        console.print(f"Run ID:        {report.optimized.run_id}")
        console.print(f"Timestamp:     {report.optimized.timestamp.isoformat()}")
        console.print()
        table = Table(show_header=True, header_style="bold", box=None)
        table.add_column("Metric")
        table.add_column("Baseline")
        table.add_column("Optimized")
        table.add_column("Savings")
        table.add_row(
            "Task latency",
            f"{report.baseline.total_latency_ms:.0f}ms",
            f"{report.optimized.total_latency_ms:.0f}ms",
            self._savings(report.latency_saved_pct),
        )
        table.add_row(
            "Cost per task",
            f"${report.baseline.estimated_cost_usd:.4f}",
            f"${report.optimized.estimated_cost_usd:.4f}",
            self._savings(report.cost_saved_pct, cost=True),
        )
        table.add_row(
            "Steps executed",
            str(report.baseline.steps_executed),
            str(report.optimized.steps_executed),
            self._savings((report.steps_reduced / report.baseline.steps_executed * 100.0) if report.baseline.steps_executed else 0.0),
        )
        table.add_row(
            "Total tokens",
            str(report.baseline.total_tokens),
            str(report.optimized.total_tokens),
            self._savings(report.tokens_saved_pct),
        )
        console.print(table)
        console.print()
        console.print("Breakdown of savings:")
        for label, pct in [
            ("Context reuse", report.context_reuse_pct),
            ("KV simulation", report.kv_simulation_pct),
            ("Graph reuse", report.graph_reuse_pct),
            ("Step reduction", report.step_reduction_pct),
        ]:
            bar = "█" * int(round(pct / 5.0))
            console.print(f"  {label:<15} {bar:<20} {pct:.0f}%")
        hits = report.optimized.steps_cached
        misses = report.optimized.steps_executed
        total = hits + misses
        hit_rate = hits / total * 100.0 if total else 0.0
        console.print()
        console.print(f"Cache:  {hits} hits / {misses} misses  (hit rate: {hit_rate:.0f}%)")
        console.print(
            f"Graph:  {report.baseline.steps_executed} nodes  ({report.optimized.steps_graph_reused} reused this run)"
        )
        return out.getvalue()

    def format_run_result(self, result: RunResult) -> str:
        """Format a workflow run result."""
        out = StringIO()
        console = Console(file=out, force_terminal=False)
        table = Table(title=f"Run {result.run_id}")
        table.add_column("Step")
        table.add_column("Decision")
        table.add_column("Input")
        table.add_column("Output")
        table.add_column("Latency")
        for step in result.step_results:
            table.add_row(step.step_id, step.decision.value, str(step.input_tokens), str(step.output_tokens), f"{step.latency_ms:.0f}ms")
        console.print(table)
        return out.getvalue()

    def format_benchmark_result(self, result: BenchmarkResult) -> str:
        """Format one benchmark result."""
        return (
            f"{result.mode}: latency={result.total_latency_ms:.0f}ms "
            f"tokens={result.total_tokens} steps={result.steps_executed}"
        )

