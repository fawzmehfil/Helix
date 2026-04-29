#!/usr/bin/env bash
set -euo pipefail

real=false
repeat=3

usage() {
  echo "Usage: $0 [--real] [--repeat N]"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --real)
      real=true
      shift
      ;;
    --repeat)
      if [ "$#" -lt 2 ]; then
        usage
        exit 1
      fi
      repeat="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage
      exit 1
      ;;
  esac
done

workflows=(
  "workflows/demo_real_partial.yaml"
  "workflows/demo_realistic_pipeline.yaml"
  "workflows/demo_low_reuse.yaml"
  "workflows/demo_token_minimization.yaml"
)

tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT
export HELIX_RUNS_DIR="$tmpdir/runs"

printf "%-38s | %8s | %8s | %8s | %9s\n" "Workflow" "Cost ↓" "Calls ↓" "Tokens ↓" "Latency ↓"
printf "%-38s-+-%8s-+-%8s-+-%8s-+-%9s\n" \
  "--------------------------------------" "--------" "--------" "--------" "---------"

for workflow in "${workflows[@]}"; do
  name=$(basename "$workflow" .yaml)
  output="$tmpdir/$name.json"
  command_output="$tmpdir/$name.out"
  cache_path="$tmpdir/$name-cache.db"
  graph_path="$tmpdir/$name-graph.db"

  bench_args=("$workflow")
  if [ "$real" = true ]; then
    bench_args+=(--real --backend openai --isolated)
  fi
  bench_args+=(
    --repeat "$repeat"
    --cache-path "$cache_path" \
    --graph-path "$graph_path" \
    --json-out "$output"
  )

  helix bench "${bench_args[@]}" >"$command_output"
  if [ ! -f "$output" ]; then
    cat "$command_output"
    exit 1
  fi
  python3 -c '
import json
import sys

workflow_path = sys.argv[1]
output_path = sys.argv[2]

with open(output_path, encoding="utf-8") as handle:
    payload = json.load(handle)

avg = payload["aggregate"]["avg"]

def reduction(baseline_key, optimized_key):
    baseline = avg[baseline_key]
    optimized = avg[optimized_key]
    return ((baseline - optimized) / baseline * 100.0) if baseline else 0.0

cost = reduction("baseline_cost_usd", "optimized_cost_usd")
calls = reduction("baseline_calls", "optimized_calls")
tokens = reduction("baseline_tokens", "optimized_tokens")
latency = reduction("baseline_latency_ms", "optimized_latency_ms")
print(
    f"{workflow_path:<38} | "
    f"{cost:>7.1f}% | "
    f"{calls:>7.1f}% | "
    f"{tokens:>7.1f}% | "
    f"{latency:>8.1f}%"
)
' "$workflow" "$output"
done
