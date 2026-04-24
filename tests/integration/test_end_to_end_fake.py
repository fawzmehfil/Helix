from helix.benchmark_engine import BenchmarkRunner
from helix.cli.commands._common import build_runner
from helix.config import HelixConfig
from helix.workflow import WorkflowParser


def test_end_to_end_fake():
    workflow = WorkflowParser().parse_file("workflows/demo_chain.yaml")
    report = BenchmarkRunner(build_runner("fake", True), build_runner("fake", False), HelixConfig.default().cost_table).run_comparison(workflow, {})
    assert report.optimized.steps_executed < report.baseline.steps_executed
    report.validate()

