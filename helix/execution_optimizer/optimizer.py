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

    def plan(self, workflow: "Workflow", run_id: str) -> OptimizationPlan:
        """For each step in workflow, produce an ExecutionDecision."""
        decisions: list[ExecutionDecision] = []
        prev_snapshot = None
        total_time = 0.0
        total_cost = 0.0
        self._snapshots = {}
        for step in workflow.steps:
            model = step.model or workflow.default_model or self.model_id
            snapshot = self.decomposer.decompose_messages(step.messages, step.step_id, run_id)
            key = CacheKey(snapshot.blocks, model)
            self._snapshots[step.step_id] = (snapshot, key, model)
            if not self.optimizations_enabled or not step.cacheable:
                kv = self.kv_simulator.estimate(prev_snapshot, snapshot, model)
                decision = ExecutionDecision(step.step_id, ExecutionDecisionType.EXECUTE, kv_estimate=kv, reason="optimizations disabled")
            else:
                entry = self.cache_store.get(key)
                if entry is not None:
                    decision = ExecutionDecision(step.step_id, ExecutionDecisionType.CACHE_HIT, cache_entry=entry, reason="cache key matched")
                else:
                    node = self.graph_reuser.find_reusable_node(snapshot, model)
                    if node is not None:
                        decision = ExecutionDecision(step.step_id, ExecutionDecisionType.GRAPH_REUSE, graph_node=node, reason="graph input hash matched")
                    else:
                        kv = self.kv_simulator.estimate(prev_snapshot, snapshot, model)
                        total_time += kv.estimated_time_saved_ms
                        total_cost += kv.estimated_cost_saved_usd
                        decision = ExecutionDecision(step.step_id, ExecutionDecisionType.EXECUTE, kv_estimate=kv, reason="no cache or graph match")
            decisions.append(decision)
            prev_snapshot = snapshot
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
                created_at=dt.datetime.utcnow(),
            )
        now = dt.datetime.utcnow()
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
