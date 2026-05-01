# Helix Engine Behavior

This file describes runtime behavior. Use it to avoid incorrect assumptions in future AI sessions.

For non-negotiable guarantees, see `AI_CONTEXT.md` -> Protected Invariants.

Product frame: Helix does not optimize prompts; it eliminates redundant execution.

## Execution Graph Model

Helix parses YAML into execution nodes. Each node has:

- `step_id`
- `step_type`
- messages/tool args
- model/backend
- dependencies (`depends_on`)
- cache settings
- optional projection, schema, semantic reuse, and token budget config

The existing YAML uses `steps` for compatibility, but product language should say **execution nodes**.

## Baseline vs Optimized Execution

Baseline:

- executes every node
- bypasses reuse decisions
- used for comparison and attribution

Optimized:

- computes cache keys from resolved/minimized inputs
- reuses exact cache hits
- checks semantic cache for opted-in nodes
- recomputes only invalidated nodes
- records per-node decisions and metrics

Decision types:

- `execute`
- `cache_hit`
- `graph_reuse`
- `skip`

## Cache Key Logic

Exact cache keys are based on:

- resolved node input context after relevant minimization/projection decisions
- model identity
- context block hashes

Cache keys must not include unrelated branch outputs or unused dependency data.

Expected behavior:

- same relevant resolved input -> same key
- changed referenced input -> different key
- changed unrelated input -> same key for unaffected nodes
- selected dependency fields narrow invalidation boundaries

## Exact Cache Behavior

On optimized execution:

1. Resolve node inputs.
2. Decompose context into blocks.
3. Build cache key.
4. If exact cache entry exists, return cached output and count a cache hit.
5. If no hit, execute provider/tool call and store result.

Cached nodes do not send provider prompts and should not create global prompt-regression warnings.

## LangGraph Adapter Behavior

LangGraph support is adapter-only:

- `HelixLangGraphRunner` wraps a compiled LangGraph graph.
- LangGraph still owns graph structure, scheduling, state merging, and control flow.
- Each LangGraph node name becomes a Helix `step_id`.
- The node input received from LangGraph is serialized and passed through existing Helix cache-key logic.
- Cache hit returns the cached node output.
- Miss executes the original LangGraph node normally and stores the output.

Trace:

- one `TraceEntry` per node decision
- decision is `cache_hit` or `execute`
- cache hit reason: `input unchanged`
- miss reason: `no cache entry` or shallow `input changed: field`
- JSON export includes trace and summary

Runtime metrics:

- adapter-local, not benchmark_engine metrics
- collected only when nodes call `helix_openai_call`
- uses actual OpenAI response `usage`
- records calls made, calls avoided, input/output/total tokens, cost, latency
- metrics do not affect cache decisions or execution order
- calls without response usage are skipped for token/cost metrics

## Semantic Reuse Behavior

Semantic reuse is opt-in per node:

```yaml
semantic_reuse: true
semantic_threshold: 0.90
```

Behavior:

1. Build minimized input text.
2. Compute embedding.
3. Search semantic cache for nearest prior input.
4. If cosine similarity >= threshold, apply review mode.
5. Accepted semantic reuse returns prior output without a provider call.
6. Rejected semantic reuse recomputes normally.

Review modes:

- `auto_accept`: default for automation
- `auto_reject`: compute similarity but never reuse
- `interactive`: prompt user for accept/reject

Config surfaces:

- `HELIX_SEMANTIC_REVIEW_MODE`
- CLI `--semantic-review auto_accept|auto_reject|interactive`

Metrics:

- semantic cache hits
- accepted/rejected
- similarity score
- embedding calls
- embedding latency
- semantic calls/tokens avoided

## Partial Recomputation

Helix invalidates by resolved input, not by broad upstream existence.

If an upstream node changes, downstream nodes recompute only if the downstream resolved input changes.

Projection narrows invalidation:

```yaml
input_projection:
  extract_metadata:
    fields: ["doc_type", "region"]
```

If `extract_metadata.output.irrelevant_notes` changes but a downstream node only uses `doc_type` and `region`, that downstream node can still reuse.

## Context Minimization

Token accounting definitions:

- `raw_input_tokens`: fully resolved unoptimized prompt/messages
- `projected_input_tokens`: after projection and unused context removal, before optimizer-added instructions
- `optimization_overhead_tokens`: instructions added by Helix, such as compact JSON guidance
- `minimized_input_tokens`: final prompt sent to provider
- `tokens_removed_by_projection`: `max(raw - projected, 0)`
- `net_tokens_saved_by_minimization`: `raw - minimized`
- `minimization_effective`: true only if net saved > 0

Projection support:

```yaml
input_projection:
  extract_metadata:
    fields: ["doc_type", "region"]
  summarize_change:
    max_words: 40
```

Field slicing:

- `{step.output}` injects full output
- `{step.output.field}` injects one JSON field
- `{step.output.a.b}` supports simple nested paths

Budgeting:

- `max_input_tokens`
- `max_dependency_tokens`

Budget trimming removes dependency content before system instructions or direct user input.

Framing note: context minimization is not the primary product claim. It supports the larger goal of fewer tokens after Helix has avoided unnecessary provider calls.

## Structured Outputs

Node config:

```yaml
output_format: json
output_schema:
  type: object
  properties:
    doc_type: {type: string}
    region: {type: string}
  required: ["doc_type", "region"]
```

Behavior:

1. Parse model output as JSON.
2. Validate JSON Schema subset: type, properties, required, basic arrays.
3. If invalid, send one schema-aware repair prompt.
4. If repair succeeds, continue with repaired JSON.
5. If repair fails, mark node failed but do not crash the entire execution.

Metrics:

- `schema_validation_failed`
- `repair_attempted`
- `repair_successful`
- `structured_output_failed`

## Parallel Execution

Enabled by `helix bench ... --parallel`.

Behavior:

- compute topological levels
- run ready independent nodes concurrently
- wait for a level to finish before downstream levels
- preserve deterministic result ordering

Current limitation: level-based scheduler, not full work-stealing or distributed scheduling.

Metrics:

- sequential estimated latency
- actual parallel latency
- critical path latency
- parallel speedup factor
- max concurrency
- parallel nodes executed

## Warning And Reporting Rules

Global regression warning only when optimized aggregate is worse than baseline for:

- latency
- cost
- tokens
- calls

Context minimization global warning only when aggregate `net_tokens_saved_by_minimization < 0`.

If one executed node has negative minimization but aggregate minimization is positive, report it as a per-node note, not a global regression.

Warnings should be deduplicated.

Semantic-only workflows should not emit minimization warnings when minimization is not active.

## Failure Modes

Watch for these when changing execution logic:

- cache key pollution: unrelated upstream outputs or unused fields enter cache keys, causing false misses
- projection failure: `input_projection` exists but raw/projected tokens do not change when they should
- semantic threshold misconfiguration: low threshold causes unsafe reuse; high threshold eliminates useful reuse
- semantic reuse leakage: approximate reuse applies to nodes without `semantic_reuse: true`
- structured output failure: invalid JSON/schema mismatch is not repaired or not marked failed safely
- parallel inefficiency: parallel mode adds overhead or loses deterministic result ordering
- incorrect invalidation boundaries: changed unrelated input recomputes stable branches, or changed relevant input reuses stale output
- warning inflation: cached/skipped nodes create global prompt/minimization warnings
- benchmark drift: CLI displays metrics not backed by `benchmark_engine` results
