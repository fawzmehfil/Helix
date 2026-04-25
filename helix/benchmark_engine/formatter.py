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
        if pct < 0:
            return f"+{abs(pct):.1f}% regression"
        return f"-{pct:.1f}%"

    def _saved_line(self, saved_pct: float, saved_value: str) -> str:
        if saved_pct < 0:
            return f"Increased: {saved_value} ({abs(saved_pct):.1f}% regression)"
        return f"Saved:     {saved_value} ({saved_pct:.1f}%)"

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
        console.print()
        console.print("Context minimization:")
        console.print(f"  Raw input tokens:        {report.optimized.raw_input_tokens}")
        console.print(f"  Projected input tokens:  {report.optimized.projected_input_tokens}")
        console.print(f"  Overhead tokens:         {report.optimized.optimization_overhead_tokens}")
        console.print(f"  Final minimized tokens:  {report.optimized.minimized_input_tokens}")
        console.print(f"  Removed by projection:   {report.optimized.tokens_removed_by_projection}")
        console.print(
            f"  Net tokens saved:        {report.optimized.net_tokens_saved_by_minimization:+d}"
        )
        if report.optimized.net_tokens_saved_by_minimization <= 0:
            console.print("  Effective:               no")
        else:
            console.print("  Effective:               yes")
        if report.warnings:
            console.print()
            console.print("WARNING: Optimization regression detected")
            for warning in report.warnings:
                console.print(f"- {warning}")
        return out.getvalue()

    def format_real_benchmark(self, report: AttributionReport) -> str:
        """Format the high-signal real API benchmark report."""
        out = StringIO()
        console = Console(file=out, force_terminal=False, width=100)
        model = next((step.model for step in report.baseline.per_step if step.model != "unknown"), "unknown")
        console.print("=== HELIX EXECUTION REPORT ===")
        console.print()
        console.print(f"Model: {model}")
        console.print()
        console.print("Latency:")
        console.print(f"Baseline:   {report.baseline.total_latency_ms / 1000.0:.2f}s")
        console.print(f"Optimized:  {report.optimized.total_latency_ms / 1000.0:.2f}s")
        console.print(
            self._saved_line(report.latency_saved_pct, f"{report.latency_saved_ms / 1000.0:.2f}s")
        )
        console.print()
        console.print("Cost:")
        console.print(f"Baseline:   ${report.baseline.estimated_cost_usd:.6f}")
        console.print(f"Optimized:  ${report.optimized.estimated_cost_usd:.6f}")
        console.print(self._saved_line(report.cost_saved_pct, f"${report.cost_saved_usd:.6f}"))
        console.print()
        console.print("Tokens:")
        console.print(f"Baseline:   {report.baseline.total_tokens}")
        console.print(f"Optimized:  {report.optimized.total_tokens}")
        console.print(self._saved_line(report.tokens_saved_pct, str(report.tokens_saved)))
        console.print()
        console.print("Calls:")
        console.print(f"Baseline:   {report.baseline.calls}")
        console.print(f"Optimized:  {report.optimized.calls}")
        console.print(f"Avoided:    {report.calls_avoided}")
        console.print()
        console.print("Call-level savings:")
        console.print(f"Calls avoided:             {report.calls_avoided}")
        console.print(f"Tokens avoided by skips:   {report.tokens_avoided}")
        console.print(f"Semantic calls avoided:    {report.semantic_calls_avoided}")
        console.print(f"Semantic tokens avoided:   {report.semantic_tokens_avoided}")
        console.print()
        console.print("Context minimization:")
        console.print(f"Raw input tokens:        {report.optimized.raw_input_tokens}")
        console.print(f"Projected input tokens:  {report.optimized.projected_input_tokens}")
        console.print(f"Overhead tokens:         {report.optimized.optimization_overhead_tokens}")
        console.print(f"Final minimized tokens:  {report.optimized.minimized_input_tokens}")
        console.print(f"Removed by projection:   {report.optimized.tokens_removed_by_projection}")
        console.print(f"Net tokens saved:        {report.optimized.net_tokens_saved_by_minimization:+d}")
        console.print(f"Budget trimmed tokens:   {report.optimized.tokens_trimmed_by_budget}")
        reduction = (
            report.optimized.net_tokens_saved_by_minimization / report.optimized.raw_input_tokens * 100.0
            if report.optimized.raw_input_tokens
            else 0.0
        )
        if report.optimized.net_tokens_saved_by_minimization > 0:
            console.print(f"Reduction:               {reduction:.1f}%")
        else:
            console.print("Reduction:               0.0% (not effective)")
        console.print()
        console.print("Attribution:")
        console.print(f"Calls avoided:             {report.calls_avoided}")
        console.print(f"Tokens avoided:            {report.tokens_avoided}")
        console.print(f"Steps skipped:             {report.optimized.steps_cached + report.optimized.steps_graph_reused + report.optimized.steps_skipped}")
        exact_cache_hits = report.optimized.steps_cached - report.optimized.semantic_cache_hits
        console.print(f"Exact cache hits:          {exact_cache_hits}")
        console.print(f"Semantic cache hits:       {report.optimized.semantic_cache_hits}")
        console.print(f"Semantic tokens avoided:   {report.semantic_tokens_avoided}")
        console.print(f"Avg similarity score:      {report.optimized.avg_similarity_score:.3f}")
        console.print(f"Graph reuse:               {report.optimized.steps_graph_reused}")
        console.print(f"Steps eliminated:          {report.steps_eliminated}")
        console.print(f"Partial recomputation:     {report.partial_recomputation_steps} reused steps")
        console.print()
        console.print("Structured output:")
        console.print(f"Repair attempts:           {report.optimized.repair_attempts}")
        console.print(f"Schema failures:           {report.optimized.schema_validation_failures}")
        success_rate = (
            report.optimized.repair_successes / report.optimized.repair_attempts * 100.0
            if report.optimized.repair_attempts
            else 0.0
        )
        console.print(f"Repair success rate:       {success_rate:.1f}%")
        console.print()
        table = Table(title="Per-step optimized metrics", box=None)
        table.add_column("step_id")
        table.add_column("decision")
        table.add_column("raw input", justify="right")
        table.add_column("projected", justify="right")
        table.add_column("removed", justify="right")
        table.add_column("overhead", justify="right")
        table.add_column("final", justify="right")
        table.add_column("net saved", justify="right")
        table.add_column("effective")
        table.add_column("budget")
        table.add_column("cache")
        table.add_column("semantic")
        table.add_column("similarity", justify="right")
        table.add_column("repair")
        table.add_column("cost", justify="right")
        table.add_column("latency", justify="right")
        for step in report.optimized.per_step:
            table.add_row(
                step.step_id,
                step.decision.value,
                str(step.raw_input_tokens),
                str(step.projected_input_tokens),
                str(step.tokens_removed_by_projection),
                str(step.optimization_overhead_tokens),
                str(step.minimized_input_tokens),
                f"{step.net_tokens_saved_by_minimization:+d}",
                "yes" if step.minimization_effective else "no",
                "yes" if step.budget_applied else "no",
                "yes" if step.cache_hit else "no",
                "yes" if step.semantic_cache_hit else "no",
                f"{step.similarity_score:.3f}" if step.semantic_reuse_applied else "-",
                "yes" if step.repair_attempted else "no",
                f"${step.estimated_cost_usd:.6f}",
                f"{step.latency_ms / 1000.0:.2f}s",
            )
        console.print(table)
        console.print()
        console.print("Warnings:")
        if report.warnings:
            console.print("WARNING: Optimization regression detected")
            for warning in report.warnings:
                console.print(f"- {warning}")
        else:
            console.print("- none")
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
