import os

import pytest
from click.testing import CliRunner

from helix.cli.main import cli


@pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="OPENAI_API_KEY is not set")
def test_openai_real_benchmark_runs_when_key_present():
    result = CliRunner().invoke(
        cli,
        ["bench", "workflows/demo_real_repeat.yaml", "--real", "--backend", "openai"],
    )

    assert result.exit_code == 0
    assert "=== HELIX EXECUTION REPORT ===" in result.output


@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="ANTHROPIC_API_KEY is not set")
def test_anthropic_real_benchmark_runs_when_key_present():
    result = CliRunner().invoke(
        cli,
        ["bench", "workflows/demo_real_repeat.yaml", "--real", "--backend", "anthropic"],
    )

    assert result.exit_code == 0
    assert "=== HELIX EXECUTION REPORT ===" in result.output
