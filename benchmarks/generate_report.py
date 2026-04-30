"""Generate Markdown reports from repeat benchmark JSON artifacts."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MANIFEST_PATH = Path(__file__).with_name("benchmark_suite.yaml")


def _read_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    """Read the fixed benchmark suite manifest without external YAML dependencies."""
    manifest: dict[str, Any] = {"workloads": []}
    current: dict[str, str] | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - "):
            current = {}
            manifest["workloads"].append(current)
            key, value = _split_key_value(line[4:])
            current[key] = value
        elif line.startswith("    ") and current is not None:
            key, value = _split_key_value(line.strip())
            current[key] = value
        elif not line.startswith(" "):
            key, value = _split_key_value(line)
            if key == "workloads" and value == "":
                manifest[key] = []
            else:
                manifest[key] = int(value) if key == "repeat" else value
    return manifest


def _split_key_value(line: str) -> tuple[str, str]:
    key, _, value = line.partition(":")
    return key.strip(), value.strip().strip('"')


def _load_results(results_dir: Path) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for path in sorted(results_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if "runs" not in payload or "aggregate" not in payload:
            continue
        results[path.stem] = payload
    return results


def _workload_key(workload: dict[str, str]) -> str:
    return Path(workload.get("path", "")).stem


def _pct_down(avg: dict[str, Any], baseline_key: str, optimized_key: str) -> str:
    baseline = _number(avg.get(baseline_key))
    optimized = _number(avg.get(optimized_key))
    if baseline == 0:
        return "N/A"
    return f"{((baseline - optimized) / baseline * 100.0):.1f}%"


def _number(value: Any) -> float:
    return float(value) if isinstance(value, int | float) else 0.0


def _metric(avg: dict[str, Any], key: str, suffix: str = "") -> str:
    if key not in avg:
        return "N/A"
    value = _number(avg[key])
    if suffix == "$":
        return f"${value:.6f}"
    if suffix == "s":
        return f"{value / 1000.0:.2f}s"
    if suffix == "%":
        return f"{value:.1f}%"
    return f"{value:.1f}"


def _notes(payload: dict[str, Any]) -> str:
    warnings = payload.get("warnings") or []
    if not warnings:
        return ""
    return "; ".join(str(warning) for warning in warnings)


def _first_timestamp(payloads: list[dict[str, Any]]) -> str:
    for payload in payloads:
        for run in payload.get("runs", []):
            timestamp = run.get("timestamp")
            if timestamp:
                return str(timestamp)
    return datetime.now(timezone.utc).isoformat()


def generate_report(results_dir: str | Path) -> Path:
    """Generate REPORT.md in a directory containing repeat benchmark JSON files."""
    root = Path(results_dir)
    manifest = _read_manifest()
    results = _load_results(root)
    workloads = manifest.get("workloads", [])
    payloads = list(results.values())
    backend = str(payloads[0].get("backend", manifest.get("backend", "unknown"))) if payloads else str(manifest.get("backend", "unknown"))
    model = str(payloads[0].get("model", manifest.get("model", "unknown"))) if payloads else str(manifest.get("model", "unknown"))
    repeat = int(manifest.get("repeat", 0))
    if payloads:
        repeat = len(payloads[0].get("runs", [])) or repeat

    lines = [
        "# Helix Benchmark Report",
        "",
        "## Summary Table",
        "",
        "Workflow | Calls ↓ | Cost ↓ | Tokens ↓ | Latency ↓ | Reuse Rate | Notes",
        "--- | ---: | ---: | ---: | ---: | ---: | ---",
    ]
    for workload in workloads:
        payload = results.get(_workload_key(workload))
        if payload is None:
            continue
        avg = payload.get("aggregate", {}).get("avg", {})
        lines.append(
            " | ".join(
                [
                    workload.get("name", _workload_key(workload)),
                    _pct_down(avg, "baseline_calls", "optimized_calls"),
                    _pct_down(avg, "baseline_cost_usd", "optimized_cost_usd"),
                    _pct_down(avg, "baseline_tokens", "optimized_tokens"),
                    _pct_down(avg, "baseline_latency_ms", "optimized_latency_ms"),
                    _metric(avg, "reuse_rate_pct", "%"),
                    _notes(payload),
                ]
            )
        )

    lines.extend(["", "## Per-Workload Breakdown", ""])
    for workload in workloads:
        payload = results.get(_workload_key(workload))
        if payload is None:
            continue
        aggregate = payload.get("aggregate", {})
        avg = aggregate.get("avg", {})
        std = aggregate.get("std", {})
        name = workload.get("name", _workload_key(workload))
        lines.extend(
            [
                f"### {name}",
                "",
                f"Description: {workload.get('description', '')}",
                "",
                "Baseline vs Optimized (avg):",
                f"- Calls: {_metric(avg, 'baseline_calls')} -> {_metric(avg, 'optimized_calls')}",
                f"- Tokens: {_metric(avg, 'baseline_tokens')} -> {_metric(avg, 'optimized_tokens')}",
                f"- Cost: {_metric(avg, 'baseline_cost_usd', '$')} -> {_metric(avg, 'optimized_cost_usd', '$')}",
                f"- Latency: {_metric(avg, 'baseline_latency_ms', 's')} -> {_metric(avg, 'optimized_latency_ms', 's')}",
                "",
                "Variance:",
                f"- latency std: {_metric(std, 'optimized_latency_ms', 's')}",
                f"- cost std: {_metric(std, 'optimized_cost_usd', '$')}",
                f"- tokens std: {_metric(std, 'optimized_tokens')}",
                "",
                "Reuse:",
                f"- reuse rate: {_metric(avg, 'reuse_rate_pct', '%')}",
                f"- recomputation ratio: {_metric(avg, 'recomputation_ratio_pct', '%')}",
                "",
                "Top-level notes:",
            ]
        )
        warnings = payload.get("warnings") or []
        lines.extend([f"- {warning}" for warning in warnings] or ["- none"])
        lines.append("")

    command = f"helix bench <workflow> --repeat {repeat} --json-out <result.json>"
    if backend == "openai":
        command = f"helix bench <workflow> --real --backend openai --repeat {repeat} --json-out <result.json>"
    lines.extend(
        [
            "## Reproducibility",
            "",
            f"- backend: {backend}",
            f"- model: {model}",
            f"- repeat count: {repeat}",
            f"- timestamp: {_first_timestamp(payloads)}",
            f"- command used: `{command}`",
            "",
        ]
    )

    report_path = root / "REPORT.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("Usage: python benchmarks/generate_report.py <benchmark_results_dir>")
        return 1
    report_path = generate_report(args[0])
    print(f"Generated {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
