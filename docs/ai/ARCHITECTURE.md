# Helix Architecture For AI Continuation

Helix is an execution engine for AI workloads. It eliminates redundant LLM calls without changing the user's system. See `AI_CONTEXT.md` for public framing, protected invariants, and optimization priorities.

## Module Map

```text
helix/
  workflow/              YAML parser, execution runner, runtime dataclasses
  execution_optimizer/   execute/reuse decisions, semantic review behavior
  cache_engine/          exact cache and semantic cache persistence
  graph_engine/          graph persistence and graph reuse support
  benchmark_engine/      baseline vs optimized measurement, cost, reporting
  api_clients/           fake, OpenAI, Anthropic, tool client protocols
  context_engine/        context blocks, hashing, decomposition
  kv_simulator/          simulated prefix-overlap/KV reuse estimates
  embeddings.py          embedding providers and cosine similarity helpers
  tokenization.py        provider-aware token counting
  cli/                   `helix` command entry points
```

## Major Responsibilities

### `helix/workflow/`

- parses YAML into `Workflow` and `WorkflowStep`
- resolves template variables and dependency outputs
- applies context minimization/projection
- executes nodes sequentially or by parallel levels
- records `StepResult` and `RunResult`

Key files:

- `parser.py`
- `runner.py`
- `types.py`

### `helix/execution_optimizer/`

- computes optimizer decisions
- checks exact cache
- checks semantic cache when enabled
- applies semantic review mode
- emits decision reasons

Key files:

- `optimizer.py`
- `types.py`

### `helix/cache_engine/`

- stores exact cache entries
- stores semantic inputs/embeddings
- performs semantic nearest-match lookup
- composes deterministic cache keys from context block hashes and model

Key files:

- `store.py`
- `types.py`

### `helix/benchmark_engine/`

- runs baseline vs optimized comparison
- aggregates per-node metrics
- calculates cost
- formats CLI reports
- writes JSON benchmark artifacts through CLI helpers

Key files:

- `runner.py`
- `collector.py`
- `formatter.py`
- `cost.py`
- `types.py`

### `helix/api_clients/`

- abstracts execution backends
- fake backend is deterministic and requires no keys
- OpenAI/Anthropic clients collect real usage, latency, cost inputs

Key files:

- `fake.py`
- `openai_client.py`
- `anthropic_client.py`
- `factory.py`
- `protocols.py`

### `helix/embeddings.py`

- embedding provider abstraction
- OpenAI embeddings when configured/available
- local deterministic fallback for tests/local semantic behavior
- cosine similarity utilities

### `helix/tokenization.py`

- provider-aware token counting
- OpenAI uses `tiktoken` when available
- Anthropic uses best available approximation
- fake/local behavior remains deterministic

### `helix/cli/`

- Click CLI
- command modules under `helix/cli/commands/`
- Rich output

## Data Flow

```text
workflow YAML
  -> WorkflowParser
  -> WorkflowRunner
  -> execution graph / dependency order
  -> ExecutionOptimizer
  -> exact cache / semantic cache lookup
  -> provider or tool call when needed
  -> cache + graph persistence
  -> BenchmarkCollector
  -> CLI report / JSON artifact
```

Critical boundary: execution metrics flow through `benchmark_engine/`. Do not invent benchmark numbers in CLI code or docs.

## Backend Abstraction

Supported execution backends:

- `fake`: deterministic local backend, no API keys
- `openai`: real OpenAI API execution
- `anthropic`: real Anthropic API execution

Helix optimizes execution. The backend handles generation.

## Storage

- exact cache: hash-based SQLite entries
- semantic cache: minimized input text + embedding + output metadata
- graph/cache persistence: paths can be overridden through CLI/env config

Relevant environment names:

- `HELIX_CACHE_PATH`
- `HELIX_GRAPH_PATH`
- `HELIX_LLM_BACKEND`
- `HELIX_SEMANTIC_REVIEW_MODE`

Do not read or modify `.env` in AI sessions.

## CLI Entry Points

```bash
helix run <workflow_path>
helix baseline <workflow_path>
helix bench <workflow_path>
```

Important `helix bench` flags:

- `--real`: use provider APIs
- `--backend fake|openai|anthropic`
- `--isolated`: temporary cache/graph storage
- `--cache-path`
- `--graph-path`
- `--json-out`
- `--parallel`
- `--semantic-review auto_accept|auto_reject|interactive`
- `--verbose`
- `--show-graph`

## Where To Make Future Changes

- context minimization: `helix/workflow/runner.py`, `helix/workflow/types.py`
- semantic reuse: `helix/embeddings.py`, `helix/execution_optimizer/`, `helix/cache_engine/`
- benchmarking/reporting: `helix/benchmark_engine/`, `helix/cli/commands/bench.py`
- provider behavior: `helix/api_clients/`, `helix/tokenization.py`
- CLI behavior: `helix/cli/commands/`
- workflow schema fields: `helix/workflow/types.py`, `helix/workflow/parser.py`
- tests: `tests/unit/` for isolated logic, `tests/integration/` for CLI/end-to-end behavior

## Drift Guards

- Preserve public CLI flags unless explicitly changing CLI behavior.
- Keep YAML compatibility; product language can say execution graph/nodes.
- Do not bypass `ExecutionOptimizer` for optimized execution.
- Do not bypass `BenchmarkRunner`/`BenchmarkCollector` for benchmark metrics.
- Do not make semantic reuse global by default; it remains node opt-in.
- Do not frame context minimization as prompt optimization; it is execution-context reduction.
