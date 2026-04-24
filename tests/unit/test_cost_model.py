from helix.benchmark_engine import estimate_cost_usd


def test_gpt_4o_mini_cost_calculation():
    assert estimate_cost_usd("gpt-4o-mini", 1_000_000, 1_000_000) == 0.75


def test_claude_3_haiku_cost_calculation():
    assert estimate_cost_usd("claude-3-haiku-20240307", 1_000_000, 1_000_000) == 1.5
