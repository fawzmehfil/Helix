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


def test_json_out_writes_repeat_benchmark_artifact(tmp_path):
    output_path = tmp_path / "repeat-results.json"

    result = CliRunner().invoke(
        cli,
        ["bench", "workflows/demo_chain.yaml", "--repeat", "2", "--json-out", str(output_path)],
    )

    assert result.exit_code == 0
    payload = json.loads(output_path.read_text())
    assert len(payload["runs"]) == 2
    assert set(payload["aggregate"]) == {"avg", "std", "min", "max"}
    assert "warnings" in payload
    assert "baseline_latency_ms" in payload["aggregate"]["avg"]
    assert "optimized_cost_usd" in payload["aggregate"]["std"]


def test_bench_default_output_is_concise():
    result = CliRunner().invoke(cli, ["bench", "workflows/demo_chain.yaml"])

    assert result.exit_code == 0
    assert "=== HELIX REPORT ===" in result.output
    assert "Computation store:" in result.output
    assert "Execution metrics:" in result.output
    assert "Helix Benchmark Results" not in result.output


def test_bench_repeat_one_preserves_single_run_metrics(tmp_path):
    normal_path = tmp_path / "normal.json"
    repeated_path = tmp_path / "repeated.json"
    normal = CliRunner().invoke(
        cli,
        ["bench", "workflows/demo_chain.yaml", "--json-out", str(normal_path)],
    )
    repeated = CliRunner().invoke(
        cli,
        ["bench", "workflows/demo_chain.yaml", "--repeat", "1", "--json-out", str(repeated_path)],
    )

    assert normal.exit_code == 0
    assert repeated.exit_code == 0
    normal_payload = json.loads(normal_path.read_text())
    repeated_payload = json.loads(repeated_path.read_text())
    assert repeated_payload["aggregate"]["avg"]["baseline_tokens"] == normal_payload["baseline"][
        "total_tokens"
    ]
    assert repeated_payload["aggregate"]["avg"]["optimized_calls"] == normal_payload["optimized"][
        "calls"
    ]


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
