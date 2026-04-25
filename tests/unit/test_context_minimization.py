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


def test_compact_json_adds_output_instruction_when_required_fields_exist():
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
    required_fields: ["doc_type"]
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

    assert "Return compact JSON only." in resolved.steps[0].messages[0]["content"]


def test_compact_json_does_not_add_unnecessary_instruction():
    workflow = WorkflowParser().parse_yaml(
        """
workflow_id: compact_noop_test
name: Compact Noop Test
steps:
  - step_id: s
    step_type: llm_call
    model: fake
    compact: true
    output_format: json
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

    assert "Return compact JSON only." not in resolved.steps[0].messages[0]["content"]


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
    required_fields: ["doc_type"]
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
    assert step.projected_input_tokens > 0
    assert step.minimized_input_tokens > 0
    assert step.optimization_overhead_tokens > 0
    assert step.net_tokens_saved_by_minimization == step.raw_input_tokens - step.minimized_input_tokens
    assert step.tokens_removed_by_projection == max(step.raw_input_tokens - step.projected_input_tokens, 0)


def test_template_field_slicing_injects_only_selected_nested_field():
    runner = build_runner("fake", baseline=False)
    outputs = {"s": {"content": '{"a":{"b":"keep","c":"drop"},"other":"drop"}'}}

    sliced = runner._resolve_text("Value={s.output.a.b}", {}, outputs)
    full = runner._resolve_text("Value={s.output}", {}, outputs)

    assert sliced == "Value=keep"
    assert "drop" in full


def test_plain_text_projection_max_words_and_chars():
    runner = build_runner("fake", baseline=False)
    response = {"content": "one two three four five. second sentence here."}

    words = runner._project_response("s", response, {"s": {"max_words": 3}})
    chars = runner._project_response("s", response, {"s": {"max_chars": 7}})
    sentence = runner._project_response("s", response, {"s": {"mode": "first_sentence"}})

    assert words == "one two three"
    assert chars == "one two"
    assert sentence == "one two three four five."


def test_prompt_budget_trims_dependency_content():
    workflow = WorkflowParser().parse_yaml(
        """
workflow_id: budget_test
name: Budget Test
steps:
  - step_id: seed
    step_type: tool_call
    model: fake
    tool_name: echo
    tool_args:
      one: "one two three four five six seven eight nine ten eleven twelve thirteen"
  - step_id: s
    step_type: llm_call
    model: fake
    depends_on: [seed]
    max_input_tokens: 8
    messages:
      - role: system
        content: "Do not remove system text."
      - role: user
        content: "Use dependency only: {seed.output}"
"""
    )
    runner = build_runner("fake", baseline=False)

    result = runner.run(workflow, {})
    step = result.step_results[1]

    assert step.budget_applied is True
    assert step.tokens_trimmed_by_budget > 0
    assert step.minimized_messages[0]["content"] == "Do not remove system text."


def test_prompt_budget_does_not_trim_direct_input_without_dependencies():
    workflow = WorkflowParser().parse_yaml(
        """
workflow_id: direct_budget_test
name: Direct Budget Test
steps:
  - step_id: s
    step_type: llm_call
    model: fake
    max_input_tokens: 8
    messages:
      - role: system
        content: "Do not remove system text."
      - role: user
        content: "one two three four five six seven eight nine ten eleven"
"""
    )
    runner = build_runner("fake", baseline=False)

    result = runner.run(workflow, {})
    step = result.step_results[0]

    assert step.budget_applied is False
    assert step.tokens_trimmed_by_budget == 0
    assert step.minimized_messages[1]["content"] == "one two three four five six seven eight nine ten eleven"
