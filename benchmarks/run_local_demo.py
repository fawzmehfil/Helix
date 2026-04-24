"""Run the local fake benchmark demo."""

from __future__ import annotations

from helix.benchmark_engine import BenchmarkRunner, ReportFormatter
from helix.cli.commands._common import build_runner
from helix.config import HelixConfig
from helix.workflow import WorkflowParser


def main() -> None:
    """Run the local demo benchmark."""
    workflow = WorkflowParser().parse_file("workflows/demo_chain.yaml")
    report = BenchmarkRunner(
        build_runner("fake", baseline=True),
        build_runner("fake", baseline=False),
        HelixConfig.default().cost_table,
    ).run_comparison(workflow, {})
    print(ReportFormatter().format_attribution(report))


if __name__ == "__main__":
    main()

