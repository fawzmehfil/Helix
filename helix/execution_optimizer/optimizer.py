"""Central execution optimizer."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid
from typing import TYPE_CHECKING, cast

from helix.cache_engine.types import CacheEntry, CacheKey
from helix.cache_engine.store import CacheStore
from helix.context_engine.decomposer import ContextDecomposer
from helix.execution_optimizer.types import ExecutionDecision, ExecutionDecisionType, OptimizationPlan
from helix.graph_engine.graph import ComputationGraph
from helix.graph_engine.reuser import GraphReuser
from helix.graph_engine.types import GraphNode
from helix.kv_simulator.simulator import KVSimulator

if TYPE_CHECKING:
    from helix.context_engine.types import ContextSnapshot
    from helix.workflow.types import Workflow


class ExecutionOptimizer:
    """Orchestrate cache, graph, and KV simulation decisions."""

    def __init__(
        self,
        decomposer: ContextDecomposer,
        cache_store: CacheStore,
        graph: ComputationGraph,
        graph_reuser: GraphReuser,
        kv_simulator: KVSimulator,
        model_id: str,
        optimizations_enabled: bool = True,
    ) -> None:
        """Create an optimizer."""
        self.decomposer = decomposer
        self.cache_store = cache_store
        self.graph = graph
        self.graph_reuser = graph_reuser
        self.kv_simulator = kv_simulator
        self.model_id = model_id
        self.optimizations_enabled = optimizations_enabled
        self._snapshots: dict[str, tuple["ContextSnapshot", CacheKey, str]] = {}
        self._previous_snapshot_by_run: dict[str, "ContextSnapshot"] = {}

    def plan(self, workflow: "Workflow", run_id: str) -> OptimizationPlan:
        """For each step in workflow, produce an ExecutionDecision."""
        decisions: list[ExecutionDecision] = []
        prev_snapshot = self._previous_snapshot_by_run.get(run_id)
        total_time = 0.0
        total_cost = 0.0
        for step in workflow.steps:
            model = step.model or workflow.default_model or self.model_id
            snapshot = self.decomposer.decompose_messages(step.messages, step.step_id, run_id)
            key = CacheKey(snapshot.blocks, model)
            semantic_input = "\n".join(str(message.get("content", "")) for message in step.messages)
            self._snapshots[step.step_id] = (snapshot, key, model)
            if not self.optimizations_enabled or not step.cacheable:
                kv = self.kv_simulator.estimate(prev_snapshot, snapshot, model)
                reason = "step is not cacheable" if not step.cacheable else "optimizations disabled"
                decision = ExecutionDecision(
                    step.step_id,
                    ExecutionDecisionType.EXECUTE,
                    kv_estimate=kv,
                    cache_key=key.key,
                    semantic_reuse_enabled=step.semantic_reuse,
                    semantic_input=semantic_input,
                    reason=reason,
                )
            else:
                entry = self.cache_store.get(key)
                if entry is not None:
                    decision = ExecutionDecision(
                        step.step_id,
                        ExecutionDecisionType.CACHE_HIT,
                        cache_entry=entry,
                        cache_key=key.key,
                        semantic_reuse_enabled=step.semantic_reuse,
                        semantic_input=semantic_input,
                        reason="resolved context and model matched cache key",
                    )
                else:
                    semantic_entry = None
                    similarity = 0.0
                    if step.semantic_reuse:
                        semantic_entry, similarity = self.cache_store.find_semantic(
                            step.step_id,
                            model,
                            semantic_input,
                            step.semantic_threshold,
                        )
                    if semantic_entry is not None:
                        decision = ExecutionDecision(
                            step.step_id,
                            ExecutionDecisionType.CACHE_HIT,
                            cache_entry=semantic_entry,
                            cache_key=key.key,
                            semantic_cache_hit=True,
                            semantic_reuse_applied=True,
                            similarity_score=similarity,
                            semantic_reuse_enabled=True,
                            semantic_input=semantic_input,
                            reason=f"semantic cache matched at {similarity:.3f}",
                        )
                    else:
                        node = self.graph_reuser.find_reusable_node(snapshot, model)
                        if node is not None:
                            decision = ExecutionDecision(
                                step.step_id,
                                ExecutionDecisionType.GRAPH_REUSE,
                                graph_node=node,
                                cache_key=key.key,
                                semantic_reuse_enabled=step.semantic_reuse,
                                semantic_input=semantic_input,
                                reason="resolved context hash matched computation graph",
                            )
                        else:
                            kv = self.kv_simulator.estimate(prev_snapshot, snapshot, model)
                            total_time += kv.estimated_time_saved_ms
                            total_cost += kv.estimated_cost_saved_usd
                            decision = ExecutionDecision(
                                step.step_id,
                                ExecutionDecisionType.EXECUTE,
                                kv_estimate=kv,
                                cache_key=key.key,
                                semantic_reuse_enabled=step.semantic_reuse,
                                semantic_input=semantic_input,
                                similarity_score=similarity,
                                reason="no cache or graph match for resolved context",
                            )
            decisions.append(decision)
            prev_snapshot = snapshot
            self._previous_snapshot_by_run[run_id] = snapshot
        return OptimizationPlan(run_id, workflow.workflow_id, decisions, total_time, total_cost)

    def record_execution(
        self,
        decision: ExecutionDecision,
        response: dict,
        latency_ms: float,
    ) -> GraphNode:
        """Store executed responses in cache and graph, or return replayed node."""
        if decision.graph_node is not None:
            return decision.graph_node
        snapshot, key, model = self._snapshots[decision.step_id]
        if decision.cache_entry is not None:
            entry = decision.cache_entry
            return GraphNode(
                node_id=str(uuid.uuid4()),
                step_id=entry.step_id,
                run_id=entry.run_id,
                input_hash=snapshot.composite_hash,
                output_hash=hashlib.sha256(json.dumps(entry.response, sort_keys=True).encode()).hexdigest(),
                response=entry.response,
                input_tokens=entry.input_tokens,
                output_tokens=entry.output_tokens,
                latency_ms=0.0,
                model_id=model,
                created_at=dt.datetime.now(dt.UTC),
            )
        now = dt.datetime.now(dt.UTC)
        entry = CacheEntry(
            key=key.key,
            step_id=decision.step_id,
            run_id=cast("ContextSnapshot", self._snapshots[decision.step_id][0]).run_id,
            response=response,
            input_tokens=int(response.get("input_tokens", 0)),
            output_tokens=int(response.get("output_tokens", 0)),
            latency_ms=latency_ms,
            created_at=now,
            expires_at=now + dt.timedelta(seconds=self.cache_store.policy.ttl_seconds)
            if self.cache_store.policy.ttl_seconds is not None
            else None,
        )
        self.cache_store.put(key, entry)
        if decision.semantic_reuse_enabled:
            self.cache_store.put_semantic(key, entry, decision.step_id, model, decision.semantic_input)
        node = GraphNode(
            node_id=str(uuid.uuid4()),
            step_id=decision.step_id,
            run_id=entry.run_id,
            input_hash=snapshot.composite_hash,
            output_hash=hashlib.sha256(json.dumps(response, sort_keys=True).encode()).hexdigest(),
            response=response,
            input_tokens=entry.input_tokens,
            output_tokens=entry.output_tokens,
            latency_ms=latency_ms,
            model_id=model,
            created_at=now,
        )
        self.graph.add_node(node)
        return node
