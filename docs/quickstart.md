# Quickstart

Install Helix in editable mode:

```bash
pip install -e ".[dev]"
```

Run a deterministic local execution benchmark:

```bash
helix baseline workflows/incremental_execution_demo.yaml
helix run workflows/incremental_execution_demo.yaml
helix bench workflows/incremental_execution_demo.yaml
```

The fake backend requires no API keys and produces stable responses for repeatable local checks.

## Baseline vs Optimized Execution

Baseline mode executes every node:

```bash
helix baseline workflows/incremental_execution_demo.yaml
```

Optimized mode uses the computation store and incremental recomputation:

```bash
helix run workflows/incremental_execution_demo.yaml
```

Benchmark both modes:

```bash
helix bench workflows/incremental_execution_demo.yaml
```

The report separates call-level savings, exact cache reuse, semantic reuse, context minimization, and parallel execution metrics.

## Execution Graph Visibility

Show dependency edges, parallel groups, and node decisions:

```bash
helix bench workflows/parallel_execution_demo.yaml --parallel --show-graph
```

## Real Backends

OpenAI and Anthropic are interchangeable execution backends:

```bash
export OPENAI_API_KEY=...
helix bench workflows/incremental_execution_demo.yaml --real --backend openai --isolated

export ANTHROPIC_API_KEY=...
helix bench workflows/incremental_execution_demo.yaml --real --backend anthropic --isolated
```

Real benchmarks skip cleanly when API keys are missing.

## Demo Execution Graphs

- `incremental_execution_demo.yaml`: incremental recomputation and projection-based invalidation narrowing
- `semantic_execution_demo.yaml`: embedding-based approximate reuse
- `parallel_execution_demo.yaml`: DAG scheduling with `--parallel`
- `demo_execution_engine_showcase.yaml`: combined showcase
- `demo_low_reuse.yaml`: failure case with little reuse
- `demo_minimization_regression.yaml`: failure case where tiny prompts expose minimization overhead

## JSON Artifacts

```bash
helix bench workflows/incremental_execution_demo.yaml --json-out results.json
```

Artifacts include baseline totals, optimized totals, per-node metrics, context minimization, semantic reuse, structured output repair, parallel metrics, warnings, and notes.

## Current Limitations

- Semantic reuse requires threshold tuning.
- Provider embeddings add small overhead.
- Parallelism is bounded by provider rate limits and dependency graph shape.
- Provider-side KV reuse is simulated, not directly controlled.
- Distributed execution is not implemented yet.
