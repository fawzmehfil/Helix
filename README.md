# Helix — Stop paying for the same LLM work over and over.

<div align="center">
  <img src="assets/helix.png" alt="logo" width="220" />
</div>

Cut your agent costs by 40–80% by eliminating redundant LLM calls, without changing your system.

Most AI systems recompute everything on every run, even when most of the work has not changed. Helix removes redundant LLM calls across multi-step workflows by reusing unchanged work and recomputing only what is necessary.

Helix sits underneath existing AI systems and optimizes execution. It is not an agent framework, not a workflow builder, and not a prompt optimizer.

> We do not optimize prompts. We eliminate redundant execution.

## The Problem

AI systems often:

- recompute entire workflows
- resend large repeated context
- rerun unchanged steps
- pay again for identical outputs

That gets expensive quickly:

- costs scale with repeated execution
- latency stacks across multi-step systems
- small input changes often trigger full recomputation

If only one part of the input changed, the unchanged work should not be paid for again.

## What Helix Does

Helix applies five execution optimizations.

### 1. Skip identical work

If a step's resolved input has not changed, Helix avoids the LLM call.

### 2. Recompute only what changed

Small updates invalidate only affected execution nodes, not the full workflow.

### 3. Send less context

Each step receives only the data it actually needs through projection, field slicing, and token budgeting.

### 4. Run steps in parallel

Independent execution branches can run simultaneously.

### 5. Optional similar-work reuse

Semantic reuse is available only when explicitly enabled and reviewed according to policy.

## Simple Example

Without Helix:

```text
small input change
  -> full pipeline reruns
  -> 10 LLM calls
  -> full cost
  -> full latency
```

With Helix:

```text
small input change
  -> reuse unchanged steps
  -> recompute only affected nodes
  -> 2-4 LLM calls
  -> 60-80% lower cost on reuse-heavy workflows
```

Actual savings depend on workflow structure, cacheability, input changes, and provider latency.

## Real Results

Source: `benchmark_results/20260427_202806/results_real_partial.json`

Real multi-step OpenAI workflow:

```text
Calls:    10 -> 2
Latency:  14.90s -> 1.59s
Cost:    $0.000340 -> $0.000057
Tokens:   1231 -> 141
```

Broader observed ranges are workload-dependent:

- 40–80% cost reduction on reuse-heavy workflows
- 30–70% latency reduction on workflows with repeated or independent work
- lower or no savings on single-step, fully unique, or tiny-prompt workloads

## Why This Matters

Today, tools make LLMs smarter and frameworks help orchestrate workflows. But most systems still assume every step runs every time.

Helix changes the execution model:

```text
same resolved input -> reuse output
changed relevant input -> recompute affected nodes
changed unrelated input -> keep cached nodes
```

Everyone is trying to make AI systems smarter. Helix makes them efficient enough to actually scale.

## Who This Is For

Helix is for teams running repeated, multi-step, partially changing AI workloads:

- agentic systems
- document-processing pipelines
- multimodal AI pipelines
- internal AI infrastructure teams
- teams with rising LLM API spend

It is not aimed at one-off single-call prompts.

## How It Works

Helix turns YAML-defined workloads into execution graphs:

1. Parse workload into execution nodes and dependencies.
2. Resolve each node's exact model input.
3. Minimize context when projection or field slicing is configured.
4. Hash resolved input + model/config.
5. Reuse unchanged computation from the cache.
6. Execute only nodes that actually need provider calls.
7. Measure calls, tokens, latency, and cost against a baseline.

Core rule:

```text
IF node input hash unchanged -> reuse previous output
ELSE -> recompute node and update downstream invalidation boundaries
```

## Quickstart

```bash
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

helix --help
helix --version
```

Run a deterministic local benchmark:

```bash
helix bench workflows/incremental_execution_demo.yaml
```

Run a real OpenAI execution benchmark:

```bash
export OPENAI_API_KEY=...
helix bench workflows/demo_real_partial.yaml --real --backend openai --isolated
```

Show the execution graph and node decisions:

```bash
helix bench workflows/parallel_execution_demo.yaml --parallel --show-graph
```

Explain where savings came from:

```bash
helix profile workflows/demo_real_partial.yaml
```

Write a machine-readable artifact:

```bash
helix bench workflows/demo_real_partial.yaml --json-out results.json
```

## CLI Report

Default output is concise and CI-friendly:

```text
=== HELIX REPORT ===

Model: gpt-4o-mini

Latency:   14.90s -> 1.59s  (-89.4%)
Cost:      $0.000340 -> $0.000057  (-83.2%)
Tokens:    1231 -> 141  (-88.5%)
Calls:     10 -> 2

Computation store:
- exact hits: 4
- semantic hits: 0
- invalidations: hash-based
- reuse rate: 80.0%

Execution metrics:
- compute avoided: 1095 tokens
- recomputation ratio: 20.0%
- dependency reuse ratio: 80.0%
```

Use `--verbose` for per-node metrics, context minimization, structured output repair, and warnings.

## Savings Profiler

`helix profile` runs the existing baseline vs optimized benchmark and explains where Helix eliminated redundant work.

```bash
helix profile workflows/demo_real_partial.yaml --json-out savings_profile.json
```

It reports:

- baseline vs optimized calls, tokens, cost, and latency
- calls avoided and percentage savings
- exact cache hits and optional semantic hits
- reuse rate and recomputation ratio
- top nodes where calls/tokens/cost/latency were avoided
- rule-based recommendations from existing benchmark metrics

The profiler does not change execution behavior. It consumes `benchmark_engine` output.

## Demos

- `demo_real_partial.yaml`: partial recomputation + context minimization
- `demo_semantic_reuse.yaml`: optional semantic reuse for similar work
- `demo_parallel_pipeline.yaml`: independent execution branches with `--parallel`
- `demo_token_minimization.yaml`: projection and field slicing reduce repeated context
- `demo_low_reuse.yaml`: failure case where unique inputs show limited benefit
- `demo_minimization_regression.yaml`: failure case where tiny prompts expose overhead
- `demo_realistic_pipeline.yaml`: production-like document workload
- `demo_execution_engine_showcase.yaml`: combined showcase

Presentation-name aliases are also available:

- `incremental_execution_demo.yaml`
- `semantic_execution_demo.yaml`
- `parallel_execution_demo.yaml`

## Context Minimization

Helix sends each step only the context it needs.

```yaml
depends_on:
  - extract_metadata

input_projection:
  extract_metadata:
    fields: ["doc_type", "region"]

messages:
  - role: user
    content: "Route {extract_metadata.output.doc_type} in {extract_metadata.output.region}"
```

`{step.output}` injects a full dependency output. `{step.output.field}` injects only the selected JSON field.

This reduces tokens and narrows invalidation boundaries.

## Optional Semantic Reuse

Semantic reuse lets Helix reuse similar prior work when exact strings differ.

It is opt-in per step:

```yaml
- step_id: summarize_invoice
  step_type: llm_call
  semantic_reuse: true
  semantic_threshold: 0.90
```

Review modes:

- `auto_accept`
- `auto_reject`
- `interactive`

Disable semantic reuse by omitting `semantic_reuse: true`.

## Structured Outputs

Execution nodes can request compact JSON and validate it against a JSON Schema subset:

```yaml
output_format: json
output_schema:
  type: object
  properties:
    doc_type: {type: string}
    region: {type: string}
  required: ["doc_type", "region"]
```

If output is invalid, Helix performs one schema-aware repair attempt. If repair fails, the node is marked failed without crashing the entire execution.

## Integration Framing

No rewrites.

Helix plugs into your existing execution path and optimizes underneath. It is designed to work across models and frameworks, but framework-specific adapters are roadmap items unless present in code.

Supported execution backends today:

- fake deterministic backend
- OpenAI
- Anthropic

## Pricing Concept

Positioning concept only; billing logic is not implemented.

> You only pay if Helix saves you money.

Example: if Helix reduces LLM cost by 50%, the customer pays around 20% and still saves 30%.

## When Helix Works Well

- repeated or similar inputs
- multi-step LLM workflows
- partially changing documents or state
- workloads with repeated context
- independent execution branches
- rising API spend from repeated runs

## When Helix Does Not Help

- single-call tasks
- fully unique inputs with no reuse
- very small prompts where overhead dominates
- workflows where every node depends on the entire prior output
- highly dynamic prompts that intentionally change every execution

No savings, no cost.

## Repository Structure

```text
helix/
  api_clients/            provider and fake backend clients
  benchmark_engine/       baseline vs optimized measurement and reporting
  cache_engine/           exact and semantic computation store
  cli/                    helix command-line interface
  context_engine/         context snapshots and KV simulation
  execution_optimizer/    cache lookup, reuse, projection, and planning decisions
  workflow/               YAML parsing and workload execution

workflows/                demo execution graphs
benchmarks/               local benchmark scripts
tests/                    unit and integration tests
docs/                     architecture and quickstart notes
```

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -x -q
ruff check helix/ tests/ benchmarks/
mypy helix/ --ignore-missing-imports
```

## Limitations

- Results depend on workflow structure, cacheability, input changes, and provider latency.
- Semantic reuse requires threshold and review-policy tuning.
- Embeddings add small latency and cost when provider embeddings are used.
- Parallel speedup is limited by provider latency, rate limits, and dependency graph shape.
- Helix does not expose provider-side KV cache controls.
- LangChain/LangGraph adapters are not implemented yet.
- Distributed execution is not implemented yet.

## Roadmap

Future work is framed as execution optimization layers:

- Phase 6: evaluator-optimizer loops
- Phase 7: LangGraph and LangChain adapters
- Phase 8: distributed execution and remote computation stores
- Later: semantic diffing, embedding-index backends, and policy-driven reuse controls

## CTA

- Try it and see how many calls your system is wasting.
- Share workflows with high repeated LLM cost.
- Introduce teams running LLM workflows at scale.

Everyone is trying to make AI systems smarter. Helix makes them efficient enough to actually scale.
