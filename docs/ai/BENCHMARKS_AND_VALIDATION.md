# Benchmarks And Validation

Use this file when validating Helix changes. Never fabricate results.

## Ground Truth Rule

- All execution optimizations must be validated by real benchmarks when they can affect calls, tokens, latency, cost, reuse, minimization, semantic reuse, or parallel execution.
- No execution change is accepted without measurement.
- JSON files under `benchmark_results/<timestamp>/` are the only trusted source for real benchmark numbers.
- Terminal summaries are useful, but final reports must cite JSON-derived values.
- LangGraph runtime metrics are not benchmark_engine results and must be reported separately.
- Do not read, print, modify, or commit `.env`.

## Latest Real Benchmark Suite

Source: `benchmark_results/20260430_191509/`

Generated report: `benchmark_results/20260430_191509/REPORT.md`

OpenAI `gpt-4o-mini`, repeat=3, aggregate averages:

| Workflow | Calls | Cost | Tokens | Latency | Reuse | Notes |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `demo_real_partial.yaml` | 10.0 -> 2.7 (-73.3%) | $0.000356 -> $0.000086 (-75.9%) | 1263.3 -> 231.7 (-81.7%) | 14.80s -> 3.46s (-76.6%) | 73.3% | no warnings |
| `demo_realistic_pipeline.yaml` | 10.0 -> 8.7 (-13.3%) | $0.000514 -> $0.000489 (-4.8%) | 1786.7 -> 1600.7 (-10.4%) | 14.53s -> 16.09s (+10.7%) | 11.1% | latency warnings |
| `demo_low_reuse.yaml` | 4.0 -> 4.0 (0.0%) | $0.000229 -> $0.000229 (+0.0%) | 625.7 -> 626.0 (+0.1%) | 6.99s -> 7.44s (+6.5%) | 0.0% | expected failure case |
| `demo_token_minimization.yaml` | 3.0 -> 0.0 (-100.0%) | $0.000432 -> $0.000000 (-100.0%) | 993.0 -> 0.0 (-100.0%) | 12.18s -> 0.00s (-100.0%) | 100.0% | no warnings |

Current headline workload: `demo_real_partial.yaml`.

Public framing from this suite result:

- fewer calls: 10.0 -> 2.7
- fewer tokens: 1263.3 -> 231.7
- lower latency: 14.80s -> 3.46s
- lower cost: $0.000356 -> $0.000086

Do not generalize this exact result to all workloads.

Derived for `demo_real_partial.yaml`:

- calls reduction: 73.3%
- reuse rate: 73.3%
- recomputation ratio: 26.7%
- context minimization reduction: 48.2%

Latest semantic-only smoke source: `benchmark_results/20260429_023259/results_semantic.json`

`demo_semantic_reuse.yaml`, OpenAI `gpt-4o-mini`:

- calls: 1 -> 0
- latency: 1.18s -> 0.00s
- tokens: 58 -> 0
- cost: $0.000022 -> $0
- semantic cache hits: 1
- accepted: 1
- avg similarity: 1.0
- warnings: none

## LangGraph Runtime Metrics (non-benchmark)

LangGraph adapter metrics are runtime summaries, not YAML benchmark artifacts.

- Source: `HelixLangGraphRunner.get_metrics_summary()` and `get_trace_json()["metrics"]`
- Scope: the most recent LangGraph run through the adapter
- Captured by: nodes that call `helix_openai_call`
- Uses: actual OpenAI response `usage`
- Includes: calls made, calls avoided, input/output/total tokens, cost, latency
- Excludes: calls with missing response usage
- Separation rule: do not mix these values with `benchmark_engine` suite numbers

Local deterministic fallback example:

- `examples/langgraph_support_agent.py` prints trace, summary, and metrics.
- Without `OPENAI_API_KEY`, calls/tokens/cost stay zero while calls avoided reflects reused nodes.
- With OpenAI available, wrapped calls add measured usage/cost/latency.

## Demo Coverage

- `demo_real_partial.yaml`: real partial recomputation, cache hits, context minimization, structured output repair metrics.
- `demo_semantic_reuse.yaml`: semantic cache hit with review mode and similarity metrics.
- `demo_parallel_pipeline.yaml`: independent execution branches with `--parallel`.
- `demo_token_minimization.yaml`: large unused context removed by projection/field slicing.
- `demo_low_reuse.yaml`: failure case; unique inputs should show little/no reuse benefit.
- `demo_minimization_regression.yaml`: failure case; tiny prompts can make optimization overhead visible.
- `demo_realistic_pipeline.yaml`: production-like document workload with multiple dependent branches.
- `customer_support_update.yaml`: agentic support ticket update; stable classification/account context, changed billing facts.
- `incremental_execution_demo.yaml`: presentation-name alias for partial recomputation.
- `semantic_execution_demo.yaml`: presentation-name alias for semantic reuse.
- `parallel_execution_demo.yaml`: presentation-name alias for parallel execution.
- `demo_execution_engine_showcase.yaml`: combined showcase.

## Benchmark Suite Commands

Preferred proof artifact command:

```bash
./scripts/run_benchmark_suite.sh --real
```

This reads `benchmarks/benchmark_suite.yaml`, writes repeat JSON files under `benchmark_results/<timestamp>/`, and generates `REPORT.md`.

Legacy targeted real benchmark command:

```bash
./scripts/run_real_benchmarks.sh
```

Rules:

- Do not hardcode API keys.
- Read results from `benchmark_results/<latest_timestamp>/`.
- Extract metrics from JSON, not from memory or guessed terminal output.
- Save real outputs under `benchmark_results/`.
- `benchmark_results/` is ignored from git; paste relevant JSON-derived numbers into AI chats when needed.

## Direct Real Commands

The targeted script currently runs these commands internally:

```bash
helix bench workflows/demo_real_partial.yaml --real --backend openai --isolated --json-out results_real_partial.json
helix bench workflows/demo_semantic_reuse.yaml --real --backend openai --isolated --semantic-review auto_accept --json-out results_semantic.json
```

Prefer the script for real validation.

## Local Validation

Run after code changes:

```bash
pytest tests/ -x -q
ruff check helix/ tests/ benchmarks/
mypy helix/ --ignore-missing-imports
```

Useful local smoke checks:

```bash
./scripts/run_benchmark_suite.sh
helix bench workflows/demo_chain.yaml
helix bench workflows/demo_token_minimization.yaml --json-out results_token_minimization.json
helix bench workflows/demo_semantic_reuse.yaml
helix bench workflows/demo_parallel_pipeline.yaml --parallel --show-graph
```

## Metrics That Matter

Primary:

- provider calls avoided
- latency reduction
- cost reduction
- token reduction
- reuse rate
- recomputation ratio

Secondary:

- context minimization reduction
- exact cache hits
- semantic hits
- semantic accepted/rejected
- avg similarity
- structured output repair attempts/successes
- parallel speedup
- max concurrency

## Derived Metric Formulas

```text
reuse_rate = (steps_cached + steps_graph_reused + steps_skipped) /
             (steps_executed + steps_cached + steps_graph_reused + steps_skipped)

recomputation_ratio = steps_executed /
                      (steps_executed + steps_cached + steps_graph_reused + steps_skipped)

context_minimization_reduction =
  net_tokens_saved_by_minimization / raw_input_tokens
```

Use percentages with one decimal place unless exactness matters.

## Interpreting Regressions

If latency/cost/tokens/calls regress:

1. Check whether optimized executed more nodes.
2. Check whether cache keys include unrelated context.
3. Check whether projection failed or raw/final tokens moved the wrong way.
4. Check semantic review mode and threshold.
5. Check provider variance before assuming code regression.
6. Compare against the previous timestamped JSON output.

Expected failure cases:

- low reuse workloads should show limited benefit
- tiny prompts may show minimization overhead
- semantic reuse can be rejected or disabled by threshold/review mode
- provider latency can regress in repeat suites even when calls/tokens/cost improve
- report generator consumes existing repeat JSON only; stale or fake-mode results must be identified by `backend`/`model`
