# Helix Architecture

Helix is an execution engine for AI workloads. It optimizes workload execution by turning YAML into an execution graph, tracking node dependencies, and reusing prior computations whenever the resolved input is unchanged.

## Execution Graph

An execution graph contains:

- execution nodes
- dependency edges
- resolved node inputs
- model/backend configuration
- versioned node outputs

Execution rule:

```text
IF resolved node input hash unchanged -> reuse
ELSE -> recompute
```

Projection narrows invalidation boundaries. If a node only uses `extract_metadata.output.region`, changes to unrelated metadata fields do not affect that node's cache key.

## Runtime Components

- `workflow/`: parses YAML and executes the graph
- `execution_optimizer/`: decides execute, exact reuse, semantic reuse, graph reuse, or skip
- `cache_engine/`: computation store for exact hashes and semantic entries
- `benchmark_engine/`: baseline vs optimized execution measurement
- `api_clients/`: interchangeable model backends
- `context_engine/`: context snapshots and KV-overlap simulation

## Computation Store

Exact reuse is hash-based. Semantic reuse is embedding-based and opt-in per node. Exact reuse is deterministic; semantic reuse is approximate and controlled by threshold plus review mode.

## Execution Backends

OpenAI, Anthropic, and the deterministic fake backend are execution units behind the same Helix interface. Helix optimizes whether a computation must happen; the backend handles generation.
