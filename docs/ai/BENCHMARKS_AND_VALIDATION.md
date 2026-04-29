# Benchmarks And Validation

Use this file when validating Helix changes. Never fabricate results.

## Ground Truth Rule

- All execution optimizations must be validated by real benchmarks when they can affect calls, tokens, latency, cost, reuse, minimization, semantic reuse, or parallel execution.
- No execution change is accepted without measurement.
- JSON files under `benchmark_results/<timestamp>/` are the only trusted source for real benchmark numbers.
- Terminal summaries are useful, but final reports must cite JSON-derived values.
- Do not read, print, modify, or commit `.env`.

## Latest Known Real Benchmark

Source: `benchmark_results/20260427_202806/results_real_partial.json`

`demo_real_partial.yaml`, OpenAI `gpt-4o-mini`:

```text
Latency: 14.90s -> 1.59s (-89.4%)
Cost:    $0.000340 -> $0.000057 (-83.2%)
Tokens:  1231 -> 141 (-88.5%)
Calls:   10 -> 2
```

Public framing from this result:

- fewer calls: 10 -> 2
- fewer tokens: 1231 -> 141
- lower latency: 14.90s -> 1.59s
- lower cost: $0.000340 -> $0.000057

Do not generalize this exact result to all workloads.

Derived:

- calls avoided: 8
- exact cache hits: 4
- reuse rate: 80.0%
- recomputation ratio: 20.0%
- context minimization: 539 raw -> 205 final tokens
- context minimization reduction: 62.0%

Source: `benchmark_results/20260427_202806/results_semantic.json`

`demo_semantic_reuse.yaml`, OpenAI `gpt-4o-mini`:

- calls: 1 -> 0
- latency: 1.09s -> 0.00s
- tokens: 54 -> 0
- cost: $0.000019 -> $0
- semantic cache hits: 1
- accepted: 1
- avg similarity: 1.0
- warnings: none

## Demo Coverage

- `demo_real_partial.yaml`: real partial recomputation, cache hits, context minimization, structured output repair metrics.
- `demo_semantic_reuse.yaml`: semantic cache hit with review mode and similarity metrics.
- `demo_parallel_pipeline.yaml`: independent execution branches with `--parallel`.
- `demo_token_minimization.yaml`: large unused context removed by projection/field slicing.
- `demo_low_reuse.yaml`: failure case; unique inputs should show little/no reuse benefit.
- `demo_minimization_regression.yaml`: failure case; tiny prompts can make optimization overhead visible.
- `demo_realistic_pipeline.yaml`: production-like document workload with multiple dependent branches.
- `incremental_execution_demo.yaml`: presentation-name alias for partial recomputation.
- `semantic_execution_demo.yaml`: presentation-name alias for semantic reuse.
- `parallel_execution_demo.yaml`: presentation-name alias for parallel execution.
- `demo_execution_engine_showcase.yaml`: combined showcase.

## Mandatory Real Benchmark Command

Use only the project script for real benchmark validation:

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

The script currently runs these commands internally:

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
