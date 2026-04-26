from helix.cli.commands._common import build_runner
from helix.execution_optimizer.types import ExecutionDecisionType
from helix.workflow import WorkflowParser


def test_realistic_pipeline_runs_end_to_end():
    workflow = WorkflowParser().parse_file("workflows/demo_realistic_pipeline.yaml")
    runner = build_runner("fake", baseline=False)
    runner.optimizer.cache_store.clear()

    result = runner.run(workflow, workflow.metadata["measured_inputs"])

    assert len(result.step_results) == 6
    assert all(step.response for step in result.step_results)


def test_execution_engine_demo_aliases_parse():
    paths = [
        "workflows/incremental_execution_demo.yaml",
        "workflows/semantic_execution_demo.yaml",
        "workflows/parallel_execution_demo.yaml",
        "workflows/demo_execution_engine_showcase.yaml",
    ]

    for path in paths:
        workflow = WorkflowParser().parse_file(path)
        assert workflow.workflow_id
        assert workflow.steps


def test_failure_case_low_reuse_has_no_cache_hits():
    workflow = WorkflowParser().parse_file("workflows/demo_low_reuse.yaml")
    runner = build_runner("fake", baseline=False)
    runner.optimizer.cache_store.clear()

    first = runner.run(workflow, workflow.metadata["measured_inputs"])
    second = runner.run(workflow, workflow.metadata["measured_inputs"])

    assert all(step.decision == ExecutionDecisionType.EXECUTE for step in first.step_results)
    assert all(step.cache_hit is False for step in second.step_results)


def test_minimization_regression_failure_case_runs():
    workflow = WorkflowParser().parse_file("workflows/demo_minimization_regression.yaml")
    runner = build_runner("fake", baseline=False)
    runner.optimizer.cache_store.clear()

    result = runner.run(workflow, workflow.metadata["measured_inputs"])

    assert len(result.step_results) == 2
    assert any(step.optimization_overhead_tokens >= 0 for step in result.step_results)


def test_cache_invalidation_recomputes_dependent_subtree_only():
    workflow = WorkflowParser().parse_yaml(
        """
workflow_id: invalidation_test
name: Invalidation Test
steps:
  - step_id: stable
    step_type: llm_call
    model: fake
    messages:
      - role: user
        content: "stable={stable_input}"
  - step_id: changed
    step_type: llm_call
    model: fake
    messages:
      - role: user
        content: "changed={changed_input}"
  - step_id: downstream
    step_type: llm_call
    model: fake
    depends_on: [changed]
    messages:
      - role: user
        content: "{changed.output}"
"""
    )
    runner = build_runner("fake", baseline=False)
    runner.optimizer.cache_store.clear()

    runner.run(workflow, {"stable_input": "A", "changed_input": "one"})
    second = runner.run(workflow, {"stable_input": "A", "changed_input": "two"})
    decisions = {step.step_id: step.decision for step in second.step_results}

    assert decisions["stable"] == ExecutionDecisionType.CACHE_HIT
    assert decisions["changed"] == ExecutionDecisionType.EXECUTE
    assert decisions["downstream"] == ExecutionDecisionType.EXECUTE
