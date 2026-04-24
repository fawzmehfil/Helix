# Helix

Helix is a computation-aware execution optimizer for LLM agent workflows. It wraps YAML-defined workflows, records deterministic context hashes, and reuses safe prior computations through SQLite-backed cache and graph stores.

Helix v0 is measurement-first and local-first. The fake backend is deterministic and requires no API keys, which makes the benchmark path reproducible on a fresh machine.

## Installation

```bash
pip install -e ".[dev]"
```

## Quickstart

```bash
helix baseline workflows/demo_chain.yaml
helix run workflows/demo_chain.yaml
helix run workflows/demo_kv_overlap.yaml --verbose
helix bench workflows/demo_chain.yaml
python benchmarks/run_kv_overlap.py
python benchmarks/run_partial_change.py
```

`baseline` executes every step without reuse. `run` uses the optimizer, checking the response cache first, then the computation graph, then executing the step. `bench` runs baseline and optimized modes and prints attribution for latency, token, and cost savings.

Verbose runs include per-step decisions, short cache keys, input and output token counts, latency, KV prefix-overlap tokens, KV reused fraction, estimated KV time and cost saved, and a human-readable decision reason.

## Modules

| Module | Purpose |
| --- | --- |
| `context_engine` | Typed context decomposition and SHA-256 hashing |
| `cache_engine` | SQLite response cache |
| `graph_engine` | SQLite computation DAG |
| `kv_simulator` | Prefix-overlap savings estimates |
| `execution_optimizer` | Cache, graph, and execute decisions |
| `benchmark_engine` | Baseline vs optimized attribution |
| `api_clients` | Fake, OpenAI, Anthropic, and tool clients |

## v0 Notes

- Package and command names are `helix`.
- Fake backend works without API keys.
- SQLite is the only persistence layer in v0.
- Rich renders CLI output.
- Cache keys are built from fully resolved prompt context and model ID.
- KV simulation estimates block-level prefix overlap between consecutive resolved step contexts. It is an estimate only; v0 does not read provider KV-cache telemetry.
- Cache hits count as context reuse. Graph reuse is attributed separately. KV savings apply only to executed steps.

## Demos

Run the KV-overlap demo:

```bash
helix run workflows/demo_kv_overlap.yaml --verbose
python benchmarks/run_kv_overlap.py
```

The workflow keeps an identical system prompt across steps and changes the user prompt, so full response-cache hits are avoided while the shared prefix produces KV overlap.

Run the partial-change demo:

```bash
python benchmarks/run_partial_change.py
```

It performs four optimized runs: cold input, repeated input, changed input, then repeated changed input. The third run demonstrates partial recomputation by reusing the unchanged style step and recomputing the steps affected by the changed document.
