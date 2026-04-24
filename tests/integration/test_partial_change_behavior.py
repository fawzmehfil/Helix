from helix.cli.commands._common import build_runner
from helix.execution_optimizer.types import ExecutionDecisionType
from helix.graph_engine import ComputationGraph
from helix.workflow import WorkflowParser


def test_partial_change_repeated_and_changed_inputs():
    workflow = WorkflowParser().parse_file("workflows/demo_partial_change.yaml")
    runner = build_runner("fake", baseline=False)
    runner.optimizer.cache_store.clear()
    graph = runner.optimizer.graph
    if isinstance(graph, ComputationGraph):
        with graph._connect() as conn:
            conn.execute("DELETE FROM graph_nodes")

    v1 = {"document": "Helix records deterministic context hashes."}
    v2 = {"document": "Helix records deterministic context hashes and estimates KV overlap."}

    run1 = runner.run(workflow, v1)
    run2 = runner.run(workflow, v1)
    run3 = runner.run(workflow, v2)
    run4 = runner.run(workflow, v2)

    assert all(step.decision == ExecutionDecisionType.EXECUTE for step in run1.step_results)
    assert all(step.cache_hit for step in run2.step_results)
    assert any(step.decision == ExecutionDecisionType.EXECUTE for step in run3.step_results)
    assert any(step.cache_hit for step in run3.step_results)
    assert all(step.cache_hit for step in run4.step_results)


def test_real_partial_demo_preserves_unaffected_branches_with_fake_backend():
    workflow = WorkflowParser().parse_file("workflows/demo_real_partial.yaml")
    runner = build_runner("fake", baseline=False)
    runner.optimizer.cache_store.clear()
    graph = runner.optimizer.graph
    if isinstance(graph, ComputationGraph):
        with graph._connect() as conn:
            conn.execute("DELETE FROM graph_nodes")

    warmup = workflow.metadata["warmup_inputs"]
    measured = workflow.metadata["measured_inputs"]

    run1 = runner.run(workflow, warmup)
    run2 = runner.run(workflow, measured)

    assert sum(1 for step in run1.step_results if step.decision == ExecutionDecisionType.EXECUTE) == 5
    assert sum(1 for step in run2.step_results if step.cache_hit) >= 2
    assert sum(1 for step in run2.step_results if step.decision == ExecutionDecisionType.EXECUTE) <= 3
