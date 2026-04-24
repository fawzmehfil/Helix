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
