#!/usr/bin/env bash
set -euo pipefail

if [ ! -f .env ]; then
  echo "Missing .env file. Create one with OPENAI_API_KEY=..."
  exit 1
fi

set -a
source .env
set +a

timestamp=$(date +"%Y%m%d_%H%M%S")
outdir="benchmark_results/$timestamp"
mkdir -p "$outdir"

echo "Running Helix real benchmarks..."
echo "Output directory: $outdir"

helix bench workflows/demo_real_partial.yaml \
  --real --backend openai --isolated \
  --json-out "$outdir/results_real_partial.json"

helix bench workflows/demo_semantic_reuse.yaml \
  --real --backend openai --isolated \
  --semantic-review auto_accept \
  --json-out "$outdir/results_semantic.json"

echo ""
echo "Done. Results saved to:"
echo "$outdir/results_real_partial.json"
echo "$outdir/results_semantic.json"
