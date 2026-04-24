from helix.cli.commands._common import build_runner
from helix.workflow import WorkflowParser


def test_project_response_selects_json_fields():
    runner = build_runner("fake", baseline=False)
    response = {"content": '{"doc_type":"invoice","region":"US","notes":"large unused text"}'}

    projected = runner._project_response(
        "extract_metadata",
        response,
        {"extract_metadata": {"fields": ["doc_type", "region"]}},
    )

    assert projected == '{"doc_type":"invoice","region":"US"}'


def test_minimized_prompt_uses_projection_and_removes_tokens():
    workflow = WorkflowParser().parse_yaml(
        """
workflow_id: projection_test
name: Projection Test
steps:
  - step_id: extract_metadata
    step_type: llm_call
    model: fake
    messages:
      - role: user
        content: "Extract metadata"
  - step_id: downstream
    step_type: llm_call
    model: fake
    depends_on: [extract_metadata]
    input_projection:
      extract_metadata:
        fields: ["doc_type", "region"]
    messages:
      - role: user
        content: "Use metadata: {extract_metadata.output}"
"""
    )
    outputs = {
        "extract_metadata": {
            "content": '{"doc_type":"invoice","region":"US","notes":"many many unused words"}'
        }
    }
    runner = build_runner("fake", baseline=False)

    raw = runner._resolve_workflow(workflow, {}, outputs, use_projection=False)
    minimized = runner._resolve_workflow(workflow, {}, outputs, use_projection=True)

    raw_tokens = runner._estimate_tokens(raw.steps[1].messages)
    minimized_tokens = runner._estimate_tokens(minimized.steps[1].messages)
    assert "notes" in raw.steps[1].messages[0]["content"]
    assert "notes" not in minimized.steps[1].messages[0]["content"]
    assert minimized_tokens < raw_tokens


def test_compact_json_adds_output_instruction():
    workflow = WorkflowParser().parse_yaml(
        """
workflow_id: compact_test
name: Compact Test
steps:
  - step_id: s
    step_type: llm_call
    model: fake
    compact: true
    output_format: json
    max_output_tokens: 80
    messages:
      - role: system
        content: "Extract fields."
      - role: user
        content: "Extract {document}"
"""
    )
    runner = build_runner("fake", baseline=False)

    resolved = runner._resolve_workflow(
        workflow,
        {"document": "invoice"},
        {},
        apply_compact=True,
    )

    assert "Return ONLY compact JSON with no explanation." in resolved.steps[0].messages[0]["content"]


def test_context_accounting_tracks_overhead_and_net_change():
    workflow = WorkflowParser().parse_yaml(
        """
workflow_id: accounting_test
name: Accounting Test
steps:
  - step_id: s
    step_type: llm_call
    model: fake
    compact: true
    output_format: json
    messages:
      - role: system
        content: "Extract."
      - role: user
        content: "Use this very long document field: {document}"
"""
    )
    runner = build_runner("fake", baseline=False)

    result = runner.run(workflow, {"document": "alpha beta gamma delta epsilon zeta eta theta"})
    step = result.step_results[0]

    assert step.raw_input_tokens > 0
    assert step.minimized_input_tokens > 0
    assert step.optimization_overhead_tokens > 0
    assert step.net_token_change == step.minimized_input_tokens - step.raw_input_tokens
    assert step.tokens_saved_by_minimization == max(
        step.raw_input_tokens - step.minimized_input_tokens,
        0,
    )
