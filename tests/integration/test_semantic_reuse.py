from helix.cli.commands._common import build_runner
from helix.execution_optimizer.types import ExecutionDecisionType
from helix.workflow import WorkflowParser


def test_semantically_similar_input_reuses_cached_output():
    workflow = WorkflowParser().parse_file("workflows/demo_semantic_reuse.yaml")
    runner = build_runner("fake", baseline=False)
    runner.optimizer.cache_store.clear()

    first = runner.run(workflow, {"request": "Summarize invoice for Acme Corp"})
    second = runner.run(workflow, {"request": "Summarize invoice for ACME Corporation"})

    assert first.step_results[0].decision == ExecutionDecisionType.EXECUTE
    assert second.step_results[0].semantic_cache_hit is True
    assert second.step_results[0].semantic_reuse_applied is True
    assert second.step_results[0].call_count == 0


def test_dissimilar_input_does_not_semantic_reuse():
    workflow = WorkflowParser().parse_file("workflows/demo_semantic_reuse.yaml")
    runner = build_runner("fake", baseline=False)
    runner.optimizer.cache_store.clear()

    runner.run(workflow, {"request": "Summarize invoice for Acme Corp"})
    second = runner.run(workflow, {"request": "Classify a legal contract dispute"})

    assert second.step_results[0].decision == ExecutionDecisionType.EXECUTE
    assert second.step_results[0].semantic_cache_hit is False
