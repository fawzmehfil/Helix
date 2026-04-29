import json

from click.testing import CliRunner

from helix.cli.main import cli


def test_profile_outputs_savings_sections():
    result = CliRunner().invoke(cli, ["profile", "workflows/demo_chain.yaml"])

    assert result.exit_code == 0
    assert "Helix Savings Profile" in result.output
    assert "Savings:" in result.output
    assert "Reuse Breakdown:" in result.output
    assert "Top Savings Nodes:" in result.output
    assert "Context Minimization:" in result.output
    assert "Recommendations:" in result.output


def test_profile_json_out_writes_structured_profile(tmp_path):
    output_path = tmp_path / "profile.json"

    result = CliRunner().invoke(
        cli,
        ["profile", "workflows/demo_chain.yaml", "--json-out", str(output_path)],
    )

    assert result.exit_code == 0
    payload = json.loads(output_path.read_text())
    assert payload["workflow_id"] == "demo_chain_v1"
    assert "calls_avoided" in payload
    assert "reuse_rate_pct" in payload
    assert "top_savings_nodes" in payload
    assert "recommendations" in payload


def test_profile_raw_report_audits_profile_values(tmp_path):
    profile_path = tmp_path / "profile.json"
    raw_path = tmp_path / "raw_report.json"

    result = CliRunner().invoke(
        cli,
        [
            "profile",
            "workflows/demo_chain.yaml",
            "--json-out",
            str(profile_path),
            "--raw-report-out",
            str(raw_path),
        ],
    )

    assert result.exit_code == 0
    profile = json.loads(profile_path.read_text())
    raw = json.loads(raw_path.read_text())
    baseline = raw["baseline"]
    optimized = raw["optimized"]
    total_nodes = (
        optimized["steps_executed"]
        + optimized["steps_cached"]
        + optimized["steps_graph_reused"]
        + optimized["steps_skipped"]
    )
    reused_nodes = (
        optimized["steps_cached"] + optimized["steps_graph_reused"] + optimized["steps_skipped"]
    )

    assert profile["baseline_calls"] == baseline["calls"]
    assert profile["optimized_calls"] == optimized["calls"]
    assert profile["calls_avoided"] == raw["savings"]["calls_avoided"]
    assert profile["tokens_saved"] == raw["savings"]["tokens_saved"]
    assert profile["exact_cache_hits"] == (
        optimized["steps_cached"] - optimized["semantic_reuse"]["hits"]
    )
    assert profile["reuse_rate_pct"] == reused_nodes / total_nodes * 100.0
    assert f"- Calls avoided:       {profile['calls_avoided']}" in result.output
    assert f"- Tokens saved:        {profile['tokens_saved']}" in result.output


def test_profile_real_flags_skip_cleanly_without_keys(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    result = CliRunner().invoke(
        cli,
        [
            "profile",
            "workflows/demo_real_partial.yaml",
            "--real",
            "--backend",
            "openai",
            "--isolated",
        ],
    )

    assert result.exit_code == 0
    assert "OpenAI real benchmark skipped" in result.output
