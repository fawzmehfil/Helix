from helix.cli.commands._common import build_runner
from helix.workflow import WorkflowParser


def _schema_step():
    workflow = WorkflowParser().parse_yaml(
        """
workflow_id: schema_test
name: Schema Test
steps:
  - step_id: s
    step_type: llm_call
    model: fake
    output_format: json
    output_schema:
      type: object
      properties:
        doc_type: {type: string}
        priority: {type: integer}
        valid: {type: boolean}
      required: ["doc_type", "priority", "valid"]
    messages:
      - role: user
        content: "Extract"
"""
    )
    return workflow.steps[0]


def test_schema_validation_accepts_valid_json():
    runner = build_runner("fake", baseline=False)
    response = {"content": '{"doc_type":"invoice","priority":3,"valid":true}'}

    assert runner._validate_structured_response(_schema_step(), response) is True


def test_schema_validation_rejects_wrong_type():
    runner = build_runner("fake", baseline=False)
    response = {"content": '{"doc_type":"invoice","priority":"3","valid":true}'}

    assert runner._validate_structured_response(_schema_step(), response) is False


def test_schema_repair_attempts_once_and_succeeds():
    class RepairClient:
        model_id = "fake"

        def call(self, messages, **kwargs):
            return {
                "content": '{"doc_type":"invoice","priority":3,"valid":true}',
                "input_tokens": 5,
                "output_tokens": 5,
                "model": self.model_id,
                "latency_ms": 1.0,
            }

        def is_available(self):
            return True

    runner = build_runner("fake", baseline=False)
    runner.llm_client = RepairClient()
    response = {"content": '{"doc_type":"invoice","priority":"3"}', "input_tokens": 2, "output_tokens": 2}

    repaired, attempted, successful, failed = runner._repair_structured_response(_schema_step(), response)

    assert attempted is True
    assert successful is True
    assert failed is False
    assert repaired["input_tokens"] == 7
