from helix.cli.commands._common import build_runner
from helix.workflow import WorkflowParser


def test_baseline_runner_executes():
    workflow = WorkflowParser().parse_file("workflows/demo_chain.yaml")
    result = build_runner("fake", baseline=True).run(workflow, {})
    assert len(result.step_results) == 4
    assert result.total_output_tokens == 80

