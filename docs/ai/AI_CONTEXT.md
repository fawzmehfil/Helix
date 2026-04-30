# Helix AI Continuation Context

Paste this file into a fresh AI/Codex session before asking it to continue Helix.

## Definition

Helix is an execution engine for AI workloads. It is not a workflow builder, prompt chaining tool, or agent framework.

Public framing: **Helix — Stop paying for the same LLM work over and over.**

One-liner: Cut your agent costs by 40–80% by eliminating redundant LLM calls, without changing your system.

Helix optimizes LLM-based execution graphs by tracking dependencies, caching intermediate computations, recomputing only changed nodes, minimizing context, and measuring real latency/cost/token impact.

Developer mental model: **Bazel for LLM workloads**.

## Core Thesis

Better models can reduce orchestration complexity, but production AI usage increases repeated computation. Helix becomes more valuable as traffic grows because it eliminates redundant execution independent of model quality.

Traditional systems recompute full AI workloads. Helix performs incremental computation:

```text
IF resolved node input hash unchanged -> reuse previous output
ELSE -> recompute only the invalidated node/subgraph
```

## Target Users

- agent startups
- document-processing systems
- multimodal AI pipelines
- internal AI infrastructure teams
- teams with multi-step LLM workloads and repeated or partially changing inputs

## Problem Solved

Repeated LLM workloads often recompute unchanged work, wasting:

- provider calls
- input/output tokens
- wall-clock latency
- API cost
- downstream context budget

Helix makes reuse and recomputation explicit, measurable, and auditable.

Use this language consistently:

- Stop paying for the same LLM work over and over.
- Eliminate redundant LLM calls.
- Only recompute what changed.
- Send each step only the context it needs.
- Run independent steps in parallel.
- Optional semantic reuse for similar work.
- No savings, no cost.
- We do not optimize prompts. We eliminate redundant execution.

Avoid:

- positioning Helix as a workflow builder, prompt optimizer, or agent framework
- overemphasizing semantic reuse
- implying provider-side KV cache control
- claiming quality improvements or unsupported integrations
- fabricating customer or benchmark results

## Protected Invariants

Do not break these guarantees:

- cache key correctness: same resolved relevant input + model/config -> same key; changed relevant input -> different key; unrelated branches excluded
- dependency-based recomputation: changed inputs invalidate only dependent nodes whose resolved inputs change
- semantic reuse opt-in: approximate reuse only when a node declares `semantic_reuse: true`
- `benchmark_engine` is the metric source of truth; CLI/JSON reports must derive from it
- every execution change must preserve baseline vs optimized comparison
- fake backend remains deterministic and keyless
- `.env` is never read, printed, modified, or committed by AI sessions

## Optimization Priority Order

Optimize in this order:

1. avoid provider calls
2. reduce tokens
3. reduce latency
4. improve reuse rate
5. improve context minimization

Lower priorities must not harm higher priorities. Example: context minimization is not acceptable if it increases provider calls, total tokens, or cost.

## Latest Headline Benchmark

Source: `benchmark_results/20260430_191509/demo_real_partial.json`

Real OpenAI repeat benchmark, `gpt-4o-mini`, `demo_real_partial.yaml`, repeat=3, aggregate averages:

```text
Latency: 14.80s -> 3.46s (-76.6%)
Cost:    $0.000356 -> $0.000086 (-75.9%)
Tokens:  1263.3 -> 231.7 (-81.7%)
Calls:   10.0 -> 2.7 (-73.3%)
```

Derived execution metrics:

- reuse rate: 73.3%
- recomputation ratio: 26.7%
- context minimization reduction: 48.2%
- warnings: none

Latest real suite report: `benchmark_results/20260430_191509/REPORT.md`.

Older semantic reuse smoke benchmark, `benchmark_results/20260429_023259/results_semantic.json`, `demo_semantic_reuse.yaml`:

- baseline calls: 1
- optimized calls: 0
- semantic cache hits: 1
- semantic reuse accepted: 1
- average similarity: 1.0
- warnings: none

## Current Capabilities

- dependency-aware exact caching
- partial recomputation
- context minimization via projection, field slicing, and budgets
- semantic reuse with embeddings and review modes
- structured JSON output validation and one repair attempt
- parallel DAG execution by topological levels
- real OpenAI/Anthropic benchmarking
- deterministic fake backend for local tests
- per-node and aggregate metrics for latency, tokens, cost, calls, reuse, semantic hits, repairs, and warnings
- repeat benchmarking with JSON `runs` plus `aggregate {avg,std,min,max}`
- benchmark suite manifest and Markdown `REPORT.md` generation from existing JSON artifacts
- customer support update demo showing stable agent steps vs changed billing facts

## Current Limitations

- no evaluator-optimizer loop yet
- no LangChain/LangGraph adapters yet
- no distributed execution yet
- semantic reuse requires threshold and review tuning
- real benchmarking depends on provider API credentials, latency variance, and rate limits
- repeat suite shows provider latency can regress even when calls/tokens/cost improve; interpret latency with variance and warnings
- low-reuse workloads may show tiny token/cost/latency regressions, which is expected failure-case evidence
- parallel execution is level-based, not a full work-stealing scheduler
- provider-side KV cache access is not controlled directly
- report generator reads existing repeat JSON only; it does not validate benchmark freshness or run benchmarks

## Hard Rules For Future AI Sessions

- Do not rebuild Helix.
- Do not remove existing features.
- Do not redesign the architecture unless explicitly requested.
- Do not print, read, modify, or commit `.env`.
- Do not hardcode API keys.
- Use `./scripts/run_benchmark_suite.sh --real` for suite proof artifacts; use `./scripts/run_real_benchmarks.sh` for legacy targeted real validation.
- Save real benchmark outputs under `benchmark_results/`.
- Never fabricate or simulate benchmark results.
- Do not use unmeasured benchmark numbers.
- Optimize for execution efficiency: incremental computation, exact/semantic reuse, context minimization, and wall-clock execution efficiency.
- Avoid feature bloat. Each phase should define non-goals.
