import json

from benchmarks.generate_report import generate_report


def test_generate_report_creates_markdown_summary(tmp_path):
    payload = {
        "workflow_id": "demo_real_partial_v1",
        "backend": "openai",
        "model": "gpt-4o-mini",
        "runs": [{"timestamp": "2026-04-30T12:00:00+00:00"}],
        "aggregate": {
            "avg": {
                "baseline_calls": 10,
                "optimized_calls": 2,
                "baseline_cost_usd": 0.001,
                "optimized_cost_usd": 0.0002,
                "baseline_tokens": 1000,
                "optimized_tokens": 250,
                "baseline_latency_ms": 5000,
                "optimized_latency_ms": 1000,
                "reuse_rate_pct": 80,
                "recomputation_ratio_pct": 20,
            },
            "std": {
                "optimized_latency_ms": 25,
                "optimized_cost_usd": 0.00001,
                "optimized_tokens": 5,
            },
            "min": {},
            "max": {},
        },
        "warnings": ["sample warning"],
    }
    (tmp_path / "demo_real_partial.json").write_text(json.dumps(payload), encoding="utf-8")

    report_path = generate_report(tmp_path)

    report = report_path.read_text(encoding="utf-8")
    assert "# Helix Benchmark Report" in report
    assert "## Summary Table" in report
    assert "Workflow | Calls ↓ | Cost ↓ | Tokens ↓ | Latency ↓ | Reuse Rate | Notes" in report
    assert "partial_recompute" in report
    assert "80.0%" in report
    assert "sample warning" in report
    assert "## Reproducibility" in report
