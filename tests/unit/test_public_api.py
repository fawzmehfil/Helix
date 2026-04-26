from helix import run_workflow


def test_run_workflow_public_api():
    result = run_workflow(
        "workflows/demo_semantic_reuse.yaml",
        {"request": "Summarize invoice for Acme Corp"},
    )

    assert result.workflow_id == "demo_semantic_reuse_v1"
    assert len(result.step_results) == 1
