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
