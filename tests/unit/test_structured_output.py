from helix.cli.commands._common import build_runner
from helix.workflow import WorkflowParser


class RepairingClient:
    model_id = "fake"

    def __init__(self):
        self.calls = 0

    def call(self, messages, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return {
                "content": "not json",
                "input_tokens": 3,
                "output_tokens": 2,
                "model": "fake",
                "finish_reason": "stop",
            }
        return {
            "content": '{"doc_type":"invoice","region":"US"}',
            "input_tokens": 5,
            "output_tokens": 4,
            "model": "fake",
            "finish_reason": "stop",
        }

    def is_available(self):
        return True


class AlwaysInvalidClient:
    model_id = "fake"

    def call(self, messages, **kwargs):
        return {
            "content": "still not json",
            "input_tokens": 3,
            "output_tokens": 2,
            "model": "fake",
            "finish_reason": "stop",
        }

    def is_available(self):
        return True


def test_invalid_json_triggers_single_successful_repair():
    workflow = WorkflowParser().parse_yaml(
        """
workflow_id: repair_test
name: Repair Test
steps:
  - step_id: extract
    step_type: llm_call
    model: fake
    output_format: json
    required_fields: ["doc_type", "region"]
    messages:
      - role: user
        content: "Extract metadata"
"""
    )
    runner = build_runner("fake", baseline=False)
    runner.llm_client = RepairingClient()

    result = runner.run(workflow, {})
    step = result.step_results[0]

    assert step.repair_attempted is True
    assert step.repair_successful is True
    assert step.structured_output_failed is False
    assert step.call_count == 2


def test_invalid_json_failed_repair_marks_step_failed():
    workflow = WorkflowParser().parse_yaml(
        """
workflow_id: failed_repair_test
name: Failed Repair Test
steps:
  - step_id: extract
    step_type: llm_call
    model: fake
    output_format: json
    required_fields: ["doc_type"]
    messages:
      - role: user
        content: "Extract metadata"
"""
    )
    runner = build_runner("fake", baseline=False)
    runner.llm_client = AlwaysInvalidClient()

    result = runner.run(workflow, {})
    step = result.step_results[0]

    assert step.repair_attempted is True
    assert step.repair_successful is False
    assert step.structured_output_failed is True
