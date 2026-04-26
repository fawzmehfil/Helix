from helix.cli.commands._common import build_runner
from helix.workflow import WorkflowParser


def test_topological_levels_group_independent_steps():
    workflow = WorkflowParser().parse_file("workflows/demo_parallel_pipeline.yaml")
    runner = build_runner("fake", baseline=False)

    levels = runner._topological_levels(workflow)

    assert levels[0] == [0, 1, 2, 3]
    assert levels[1] == [4]


def test_parallel_run_preserves_step_order_and_reports_speedup():
    workflow = WorkflowParser().parse_file("workflows/demo_parallel_pipeline.yaml")
    runner = build_runner("fake", baseline=False)
    runner.optimizer.cache_store.clear()

    result = runner.run_parallel(workflow, {"document": "invoice with risks actions and entities"})

    assert [step.step_id for step in result.step_results] == [step.step_id for step in workflow.steps]
    assert result.max_concurrency >= 3
    assert result.parallel_speedup_factor > 1.0
    assert result.sequential_estimated_latency_ms > result.actual_parallel_latency_ms


def test_parallel_cache_writes_are_reusable():
    workflow = WorkflowParser().parse_yaml(
        """
workflow_id: parallel_cache_test
name: Parallel Cache Test
steps:
  - step_id: a
    step_type: llm_call
    model: fake
    messages:
      - role: user
        content: "A {document}"
  - step_id: b
    step_type: llm_call
    model: fake
    messages:
      - role: user
        content: "B {document}"
  - step_id: c
    step_type: llm_call
    model: fake
    depends_on: [a, b]
    messages:
      - role: user
        content: "{a.output} {b.output}"
"""
    )
    runner = build_runner("fake", baseline=False)
    runner.optimizer.cache_store.clear()

    runner.run_parallel(workflow, {"document": "invoice with risks actions and entities"})
    second = runner.run_parallel(workflow, {"document": "invoice with risks actions and entities"})

    assert all(step.cache_hit for step in second.step_results)
