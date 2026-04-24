from helix.benchmark_engine import BenchmarkRunner, ReportFormatter
from helix.cli.commands._common import build_runner
from helix.config import HelixConfig
from helix.workflow import WorkflowParser


def test_report_formatter_contains_header():
    workflow = WorkflowParser().parse_file("workflows/demo_chain.yaml")
    report = BenchmarkRunner(build_runner("fake", True), build_runner("fake", False), HelixConfig.default().cost_table).run_comparison(workflow, {})
    assert "Helix Benchmark Results" in ReportFormatter().format_attribution(report)

