from helix.cli.commands._common import build_runner
from helix.execution_optimizer.types import ExecutionDecisionType
from helix.workflow import WorkflowParser


WORKFLOW = """
workflow_id: semantic_review_test
name: Semantic Review Test
steps:
  - step_id: summarize
    step_type: llm_call
    model: fake
    semantic_reuse: true
    semantic_threshold: 0.90
    messages:
      - role: user
        content: "{request}"
"""


def test_semantic_review_auto_accept_reuses_candidate():
    workflow = WorkflowParser().parse_yaml(WORKFLOW)
    runner = build_runner("fake", baseline=False)
    runner.optimizer.semantic_review_mode = "auto_accept"
    runner.optimizer.cache_store.clear()

    runner.run(workflow, {"request": "Summarize invoice for Acme Corp"})
    second = runner.run(workflow, {"request": "Summarize invoice for ACME Corporation"})

    assert second.step_results[0].semantic_cache_hit is True
    assert second.step_results[0].semantic_reuse_accepted is True
    assert second.step_results[0].embedding_calls >= 0


def test_semantic_review_auto_reject_recomputes_candidate():
    workflow = WorkflowParser().parse_yaml(WORKFLOW)
    runner = build_runner("fake", baseline=False)
    runner.optimizer.semantic_review_mode = "auto_reject"
    runner.optimizer.cache_store.clear()

    runner.run(workflow, {"request": "Summarize invoice for Acme Corp"})
    second = runner.run(workflow, {"request": "Summarize invoice for ACME Corporation"})

    assert second.step_results[0].decision == ExecutionDecisionType.EXECUTE
    assert second.step_results[0].semantic_cache_hit is False
    assert second.step_results[0].semantic_reuse_rejected is True


def test_semantic_only_workflow_has_no_minimization_warnings():
    workflow = WorkflowParser().parse_yaml(WORKFLOW)
    runner = build_runner("fake", baseline=False)
    runner.optimizer.cache_store.clear()

    result = runner.run(workflow, {"request": "Summarize invoice for Acme Corp"})

    assert result.step_results[0].minimization_warnings == []
