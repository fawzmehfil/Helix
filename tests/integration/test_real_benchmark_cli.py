import json

from click.testing import CliRunner

from helix.cli.main import cli


def test_real_benchmark_skips_without_keys(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    result = CliRunner().invoke(cli, ["bench", "workflows/demo_real_repeat.yaml", "--real"])

    assert result.exit_code == 0
    assert "Real benchmark skipped" in result.output


def test_json_out_writes_benchmark_artifact(tmp_path):
    output_path = tmp_path / "results.json"

    result = CliRunner().invoke(
        cli,
        ["bench", "workflows/demo_chain.yaml", "--json-out", str(output_path)],
    )

    assert result.exit_code == 0
    payload = json.loads(output_path.read_text())
    assert payload["workflow_id"] == "demo_chain_v1"
    assert "baseline" in payload
    assert "optimized" in payload
    assert "warnings" in payload
    assert "context_minimization" in payload


def test_bench_default_output_is_concise():
    result = CliRunner().invoke(cli, ["bench", "workflows/demo_chain.yaml"])

    assert result.exit_code == 0
    assert "=== HELIX REPORT ===" in result.output
    assert "Computation store:" in result.output
    assert "Execution metrics:" in result.output
    assert "Helix Benchmark Results" not in result.output


def test_bench_show_graph_outputs_execution_graph():
    result = CliRunner().invoke(
        cli,
        ["bench", "workflows/parallel_execution_demo.yaml", "--parallel", "--show-graph"],
    )

    assert result.exit_code == 0
    assert "Execution graph:" in result.output
    assert "Parallel groups:" in result.output
    assert "Node decisions:" in result.output
    assert "extract_metadata -> aggregate_report" in result.output


def test_bench_verbose_output_keeps_detailed_report():
    result = CliRunner().invoke(cli, ["bench", "workflows/demo_chain.yaml", "--verbose"])

    assert result.exit_code == 0
    assert "Helix Benchmark Results" in result.output


def test_semantic_review_default_does_not_prompt():
    result = CliRunner().invoke(cli, ["bench", "workflows/demo_semantic_reuse.yaml"])

    assert result.exit_code == 0
    assert "Decision [accept/reject]" not in result.output


def test_isolated_flags_are_accepted_without_real_keys(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    result = CliRunner().invoke(
        cli,
        [
            "bench",
            "workflows/demo_real_repeat.yaml",
            "--real",
            "--isolated",
            "--cache-path",
            str(tmp_path / "cache.db"),
            "--graph-path",
            str(tmp_path / "graph.db"),
        ],
    )

    assert result.exit_code == 0
    assert "Real benchmark skipped" in result.output
