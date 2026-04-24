from helix.cli.commands._common import build_runner
from helix.workflow import WorkflowParser


def test_optimized_second_run_cache_hits():
    workflow = WorkflowParser().parse_file("workflows/demo_chain.yaml")
    runner = build_runner("fake", baseline=False)
    first = runner.run(workflow, {})
    second = runner.run(workflow, {})
    assert len(first.step_results) == 4
    assert all(step.cache_hit for step in second.step_results)

