# Helix: A Compiler for Efficient LLM Execution

[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)](#quickstart)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)
[![CLI](https://img.shields.io/badge/CLI-helix-black)](helix/cli)

Helix reduces LLM cost and latency by 50-90% by reusing previous computations, minimizing context, and executing workflows efficiently.

![Helix banner](assets/Helix_dark_banner.png)

## Problem

Most LLM pipelines recompute everything.

A document changes by one sentence. An agent retries a downstream step. A user asks the same thing with slightly different wording. The pipeline often pays for the full chain again: every prompt, every token, every API call.

That makes multi-step LLM systems slow and expensive exactly when they start to look production-ready.

## Solution

Helix treats an LLM workflow like an execution graph.

It builds a dependency DAG, hashes resolved step inputs, caches step outputs, recomputes only what changed, minimizes prompt context, reuses semantically similar results, validates structured outputs, and runs independent steps in parallel.

In short: Helix avoids unnecessary LLM work.

## Real Results

Latest real OpenAI benchmark:

```text
Latency: 11.90s -> 1.83s    (-84.6%)
Cost:    $0.000348 -> $0.000057  (-83.6%)
Tokens:  1204 -> 141       (-88.3%)
Calls:   10 -> 2

Context minimization:
Raw: 445 -> Final: 211     (-52.6%)
```

Where the savings come from:

- Calls avoided: exact cache hits, partial recomputation, and semantic reuse skip provider calls.
- Tokens avoided: projected prompts pass only needed fields downstream.
- Latency reduced: skipped calls and parallel DAG execution reduce wall-clock time.

## How It Works

1. Define a workflow in YAML.
2. Helix builds a dependency graph.
3. Each step gets a resolved input hash.
4. Helix reuses cached or semantically similar outputs when safe.
5. Changed inputs recompute only affected steps.
6. Independent branches can run concurrently.

```mermaid
flowchart LR
    A["YAML workflow"] --> B["DAG planner"]
    B --> C["Context projection"]
    C --> D["Cache + semantic reuse"]
    D --> E["Execute changed steps"]
    E --> F["Metrics + JSON report"]
```

## Quickstart

```bash
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

export OPENAI_API_KEY=...

helix bench workflows/demo_real_partial.yaml --real --backend openai --isolated
```

No API key? Use the deterministic fake backend:

```bash
helix bench workflows/demo_parallel_pipeline.yaml --parallel
```

## Demos

All demos live in [workflows/](workflows).

### `demo_real_partial.yaml`

Shows partial recomputation and context minimization.

Run:

```bash
helix bench workflows/demo_real_partial.yaml --real --backend openai --isolated
```

Expect most stable steps to hit cache after warmup, changed document fields to recompute, and projected JSON fields to reduce prompt tokens.

### `demo_semantic_reuse.yaml`

Shows embedding-based semantic reuse.

Run:

```bash
HELIX_SEMANTIC_REVIEW_MODE=auto_accept \
helix bench workflows/demo_semantic_reuse.yaml --real --backend openai --isolated
```

Expect an exact cache miss but a semantic cache hit for similar wording, such as "Acme Corp" vs "ACME Corporation".

### `demo_parallel_pipeline.yaml`

Shows parallel execution across independent DAG branches.

Run:

```bash
helix bench workflows/demo_parallel_pipeline.yaml --parallel
```

Expect the first four extraction branches to run concurrently, followed by one aggregation step. On the fake backend this typically shows `max_concurrency >= 4` and a visible latency speedup.

### `demo_showcase.yaml`

Flagship workflow combining partial recomputation, context minimization, semantic reuse, and parallel branches.

Run:

```bash
HELIX_SEMANTIC_REVIEW_MODE=auto_accept \
helix bench workflows/demo_showcase.yaml --parallel
```

Use the fake backend for a fast local tour, or switch to `--real --backend openai --isolated` with an API key.

## Key Features

- Partial recomputation
- Context minimization with projection and field slicing
- Semantic reuse with embeddings and review mode
- Parallel DAG execution
- Structured output validation and repair
- Real cost, latency, token, and call benchmarking
- JSON benchmark artifacts with per-step metrics

## Python API

```python
from helix import run_workflow

result = run_workflow("workflows/demo_real_partial.yaml", {
    "doc_type": "invoice",
    "region": "US",
    "body": "Invoice 1007 from Acme Medical...",
})
```

This is a thin wrapper around the existing runner. The CLI remains the best way to run benchmark comparisons.

## Repo Structure

```text
helix/
  api_clients/          OpenAI, Anthropic, fake, and tool clients
  benchmark_engine/     Baseline vs optimized reports
  cache_engine/         SQLite response and semantic cache
  context_engine/       Context decomposition and hashing
  execution_optimizer/  Cache, graph, semantic, and execution decisions
  graph_engine/         SQLite computation graph
  workflow/             YAML parser and workflow runner
workflows/              Demo workflows
benchmarks/             Scripted benchmark demos
tests/                  Unit and integration tests
```

## When To Use Helix

Use Helix for:

- Multi-step LLM pipelines
- Document processing systems
- Agent workflows with repeated sub-tasks
- Extraction, classification, validation, and summarization chains
- Workflows where small input changes should not trigger full recomputation

## Limitations

- Semantic reuse requires threshold tuning.
- Embeddings add small overhead.
- Parallelism is limited by provider rate limits.
- Helix is not distributed yet.
- Provider KV-cache internals are not exposed; Helix reports its own reuse and minimization metrics.

## Roadmap

- Phase 6: evaluator-optimizer loops
- Phase 7: LangChain and LangGraph adapters
- Phase 8: distributed execution
