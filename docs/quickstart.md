# Quickstart

Install Helix in editable mode:

```bash
pip install -e ".[dev]"
```

Run the local deterministic workflow:

```bash
helix baseline workflows/demo_chain.yaml
helix run workflows/demo_chain.yaml
helix bench workflows/demo_chain.yaml
```

The fake backend requires no API keys and produces stable SHA-256 responses for repeatable benchmarks.

## Baseline vs Optimized

Use baseline mode to measure full execution:

```bash
helix baseline workflows/demo_chain.yaml
```

Use optimized mode to reuse prior work:

```bash
helix run workflows/demo_chain.yaml
```

Compare both modes:

```bash
helix bench workflows/demo_chain.yaml
```

The benchmark report separates cache reuse, graph reuse, KV simulation, and remaining step reduction. Cache hits count toward context reuse. Graph reuse is counted separately. KV simulation contributes only when a step still executes.

## KV Overlap Demo

```bash
helix run workflows/demo_kv_overlap.yaml --verbose
python benchmarks/run_kv_overlap.py
```

The demo uses the same system prompt across steps and different user prompts. That prevents full cache hits while still producing block-level prefix overlap for the KV simulator.

Verbose output includes:

- step ID
- execution decision
- short cache key
- input and output tokens
- latency
- KV prefix-overlap tokens
- KV reused fraction
- estimated KV time and cost saved
- decision reason

## Partial-Change Demo

```bash
python benchmarks/run_partial_change.py
```

The script runs four cases:

1. Run 1: cold input, execute all steps.
2. Run 2: same input, cache hits.
3. Run 3: changed input, partial recompute.
4. Run 4: same changed input, cache hits.

It prints a comparison table with run number, input version, steps executed, cache hits, graph reuse, tokens, and latency.

## Current Limitations

- v0 persistence is SQLite only.
- KV savings are simulated from resolved context block overlap, not provider-side KV telemetry.
- The fake backend is deterministic and useful for local benchmarking, but it does not model provider-specific latency variance.
- Cache and graph reuse are exact-hash based; semantic equivalence is outside v0 scope.
