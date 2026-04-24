from helix.cache_engine import CacheKey
from helix.cli.commands._common import build_runner
from helix.context_engine import ContextDecomposer, SemanticHasher
from helix.workflow import WorkflowParser


def test_cache_key_stable():
    snap = ContextDecomposer(SemanticHasher()).decompose_string("hello", "s", "r")
    assert CacheKey(snap.blocks, "fake") == CacheKey(snap.blocks, "fake")


def test_cache_key_uses_resolved_context():
    workflow = WorkflowParser().parse_yaml(
        """
workflow_id: cache_key_resolution
name: Cache key resolution
steps:
  - step_id: summarize
    step_type: llm_call
    model: fake
    messages:
      - role: system
        content: "You summarize documents."
      - role: user
        content: "Summarize: {document}"
"""
    )
    runner = build_runner("fake", baseline=False)

    first = runner.run(workflow, {"document": "alpha"})
    second = runner.run(workflow, {"document": "alpha"})
    third = runner.run(workflow, {"document": "beta"})

    first_key = first.optimization_plan.decisions[0].cache_key
    second_key = second.optimization_plan.decisions[0].cache_key
    third_key = third.optimization_plan.decisions[0].cache_key
    assert first_key == second_key
    assert first_key != third_key


def test_cache_key_ignores_unreferenced_input():
    workflow = WorkflowParser().parse_yaml(
        """
workflow_id: cache_key_unrelated_input
name: Cache key unrelated input
steps:
  - step_id: classify
    step_type: llm_call
    model: fake
    messages:
      - role: user
        content: "Classify doc_type={doc_type}"
"""
    )
    runner = build_runner("fake", baseline=False)

    first = runner.run(workflow, {"doc_type": "invoice", "body": "alpha"})
    second = runner.run(workflow, {"doc_type": "invoice", "body": "beta"})
    third = runner.run(workflow, {"doc_type": "receipt", "body": "beta"})

    assert first.optimization_plan.decisions[0].cache_key == second.optimization_plan.decisions[0].cache_key
    assert first.optimization_plan.decisions[0].cache_key != third.optimization_plan.decisions[0].cache_key


def test_projection_cache_key_ignores_unselected_fields():
    workflow = WorkflowParser().parse_yaml(
        """
workflow_id: projection_cache_key
name: Projection cache key
steps:
  - step_id: extract_metadata
    step_type: llm_call
    model: fake
    messages:
      - role: user
        content: "Extract metadata"
  - step_id: classify
    step_type: llm_call
    model: fake
    depends_on: [extract_metadata]
    input_projection:
      extract_metadata:
        fields: ["doc_type"]
    messages:
      - role: user
        content: "Classify {extract_metadata.output}"
"""
    )
    runner = build_runner("fake", baseline=False)
    first = runner._resolve_workflow(
        workflow,
        {},
        {"extract_metadata": {"content": '{"doc_type":"invoice","notes":"alpha"}'}},
        use_projection=True,
    )
    second = runner._resolve_workflow(
        workflow,
        {},
        {"extract_metadata": {"content": '{"doc_type":"invoice","notes":"beta"}'}},
        use_projection=True,
    )
    third = runner._resolve_workflow(
        workflow,
        {},
        {"extract_metadata": {"content": '{"doc_type":"receipt","notes":"beta"}'}},
        use_projection=True,
    )
    decomposer = ContextDecomposer(SemanticHasher())
    snap_a = decomposer.decompose_messages(first.steps[1].messages, "classify", "r")
    snap_b = decomposer.decompose_messages(second.steps[1].messages, "classify", "r")
    snap_c = decomposer.decompose_messages(third.steps[1].messages, "classify", "r")

    assert CacheKey(snap_a.blocks, "fake") == CacheKey(snap_b.blocks, "fake")
    assert CacheKey(snap_a.blocks, "fake") != CacheKey(snap_c.blocks, "fake")
