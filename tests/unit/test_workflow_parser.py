import pytest

from helix.exceptions import WorkflowValidationError
from helix.workflow import WorkflowParser


def test_parse_examples():
    parser = WorkflowParser()
    assert parser.parse_file("workflows/demo_chain.yaml").workflow_id == "demo_chain_v1"
    assert parser.parse_file("workflows/demo_summarize.yaml").steps
    assert parser.parse_file("workflows/demo_partial_change.yaml").steps


def test_invalid_empty():
    with pytest.raises(WorkflowValidationError):
        WorkflowParser().parse_yaml("workflow_id: x\nsteps: []\n")

