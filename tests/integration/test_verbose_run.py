from click.testing import CliRunner

from helix.cli.main import cli


def test_verbose_run_includes_kv_fields():
    result = CliRunner().invoke(cli, ["run", "workflows/demo_kv_overlap.yaml", "--verbose"])

    assert result.exit_code == 0
    assert "KV overlap" in result.output
    assert "KV reused" in result.output
    assert "KV time saved" in result.output
    assert "KV cost saved" in result.output
