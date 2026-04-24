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
helix bench workflows/demo_chain.yaml
```

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

