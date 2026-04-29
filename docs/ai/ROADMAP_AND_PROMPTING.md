# Roadmap And Prompting Guide

Use this file to write future Helix prompts that are scoped and technically defensible.

See `AI_CONTEXT.md` for protected invariants and optimization priority order.

## Completed Phases

- v0 foundation: YAML execution, fake backend, exact cache, graph persistence.
- Real API benchmarking: OpenAI/Anthropic paths, cost/token/latency metrics.
- Partial recomputation: changed inputs invalidate affected nodes only.
- Semantic reuse: embedding-based approximate reuse with review modes.
- Token minimization: projection, field slicing, budget trimming, context accounting.
- Provider-aware token accounting and schema validation.
- Warning/report cleanup: aggregate regressions vs per-node notes.
- Parallel DAG execution: level-based concurrent execution.
- README/demo polish: execution-engine positioning and showcase demos.
- Credibility hardening: realistic/failure workflows and documented limitations.

## Product Direction

Helix is an execution engine for AI workloads.

Public headline: Stop paying for the same LLM work over and over.

Core claim: Cut agent costs by eliminating redundant LLM calls, without changing the user's system.

Useful mental models:

- Bazel-style incremental computation for LLM systems.
- Git-style reuse of unchanged computation state.
- Runtime optimization layer, not an agent framework.

Value proposition:

- avoid redundant provider calls
- reduce tokens and cost
- reduce wall-clock latency
- make reuse/recomputation measurable

Messaging guardrails:

- Say "We do not optimize prompts. We eliminate redundant execution."
- Keep semantic reuse optional and secondary.
- Do not claim unsupported integrations.
- Do not imply provider-side KV cache control.

## Phase 6: Evaluator-Optimizer Loops

Goal:

- evaluate multiple execution variants and choose the best quality/cost tradeoff.

Non-goals:

- no full agent framework
- no prompt marketplace
- no distributed execution
- no LangChain/LangGraph adapter in this phase

Likely implementation:

- add variant generation in `execution_optimizer/`
- add scoring/quality metrics in `benchmark_engine/`
- add YAML fields for evaluation policy only if needed
- keep existing exact/semantic cache behavior intact

Success criteria:

- variants are measured, not guessed
- selected variant improves cost-per-score or latency-per-score
- JSON artifact records variant scores
- existing benchmarks do not regress

Validation:

```bash
pytest tests/ -x -q
ruff check helix/ tests/ benchmarks/
mypy helix/ --ignore-missing-imports
./scripts/run_real_benchmarks.sh
```

## Phase 7: LangChain/LangGraph Adapters

Goal:

- let existing LangChain/LangGraph users run workloads through Helix execution optimization.

Non-goals:

- do not replace Helix YAML
- do not embed LangChain as a core dependency if optional adapters suffice
- do not change cache key semantics

Likely files:

- new adapter package, e.g. `helix/adapters/`
- tests under `tests/integration/`
- docs under `docs/`

Success criteria:

- small LangGraph-style graph maps to Helix execution graph
- dependency boundaries remain explicit
- existing YAML flows still pass
- adapter is optional

Validation:

```bash
pytest tests/ -x -q
ruff check helix/ tests/ benchmarks/
mypy helix/ --ignore-missing-imports
```

Run real benchmarks only if adapter changes affect execution behavior.

## Phase 8: Distributed Execution

Goal:

- support remote/shared computation store and distributed node execution.

Non-goals:

- no premature cluster scheduler rewrite
- no provider-specific lock-in
- no weakening cache correctness for speed

Likely files:

- `cache_engine/`
- `graph_engine/`
- `workflow/runner.py`
- new storage/locking abstractions
- benchmark artifacts for local vs remote store overhead

Success criteria:

- shared cache works across processes/machines
- cache writes are safe under concurrency
- distributed overhead is visible in metrics
- local SQLite mode remains supported

Validation:

```bash
pytest tests/ -x -q
ruff check helix/ tests/ benchmarks/
mypy helix/ --ignore-missing-imports
./scripts/run_real_benchmarks.sh
```

## Decision Constraints

Every phase must:

- preserve protected invariants from `AI_CONTEXT.md`
- not regress latency, cost, tokens, calls, or reuse rate without an explicit accepted tradeoff
- be measurable with existing benchmarks or add a narrowly scoped benchmark
- avoid unvalidated runtime behavior
- keep baseline vs optimized comparison intact
- define non-goals before implementation
- run tests/lint/typecheck
- run `./scripts/run_real_benchmarks.sh` if execution behavior changes

## Prompt-Writing Rules

Always include:

- current measured benchmark state
- exact goals
- non-goals
- files/modules likely affected
- required tests/lint/typecheck
- real benchmark validation if execution changes
- instruction not to read/print/modify/commit `.env`

Never ask Codex to:

- rebuild Helix from scratch
- remove existing capabilities
- hardcode API keys
- fabricate benchmarks
- implement multiple major phases at once

Prefer one phase per prompt. Avoid feature soup.

## Reusable Prompt Preamble

```text
You are continuing Helix.

Helix is an execution engine for AI workloads, not a workflow builder.
Public framing: stop paying for the same LLM work over and over.
Do not rebuild Helix.
Do not remove existing features.
Use docs/ai/* as source of truth.

Do not read, print, modify, or commit .env.
Use ./scripts/run_real_benchmarks.sh for real validation when execution changes.
Read benchmark numbers from benchmark_results/<latest_timestamp>/ JSON files.

Optimize for execution efficiency:
- incremental computation
- exact and semantic reuse
- context minimization
- execution latency/cost/token reduction

Define non-goals.
Run tests, lint, and typecheck.
Never fabricate benchmark results.
```

## Benchmark Reporting Template

```text
Files changed:
- ...

Validation:
- pytest tests/ -x -q: ...
- ruff check helix/ tests/ benchmarks/: ...
- mypy helix/ --ignore-missing-imports: ...

Real benchmark:
- timestamp directory: benchmark_results/<timestamp>/
- latency: baseline -> optimized
- cost: baseline -> optimized
- tokens: baseline -> optimized
- calls: baseline -> optimized
- reuse rate:
- recomputation ratio:
- context minimization reduction:

Comparison vs previous run:
- ...

Regressions:
- none / explain

Next recommended improvement:
- ...
```
