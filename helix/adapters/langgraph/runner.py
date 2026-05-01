"""Helix runner for LangGraph workflows."""

from __future__ import annotations

import copy
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any

from helix.cache_engine import CacheStore
from helix.config import HelixConfig
from helix.context_engine import ContextDecomposer, SemanticHasher
from helix.embeddings import build_embedding_provider
from helix.execution_optimizer import ExecutionOptimizer
from helix.execution_optimizer.types import ExecutionDecisionType
from helix.graph_engine import ComputationGraph, GraphReuser
from helix.kv_simulator import KVSimulator
from helix.workflow.types import Workflow, WorkflowStep, WorkflowStepType

from .utils import ensure_cacheable_output, ensure_langgraph_available, stable_json


@dataclass(frozen=True)
class LangGraphNodeEvent:
    """Execution decision for one LangGraph node."""

    step_id: str
    decision: ExecutionDecisionType
    cache_key: str | None
    reason: str


class HelixLangGraphRunner:
    """Wrap a compiled LangGraph graph with Helix per-node caching."""

    def __init__(
        self,
        graph: Any,
        *,
        config: HelixConfig | None = None,
        optimizer: ExecutionOptimizer | None = None,
        cache_path: str | None = None,
        graph_path: str | None = None,
        model_id: str = "langgraph",
    ) -> None:
        """Create a LangGraph runner that preserves LangGraph execution semantics."""
        ensure_langgraph_available()
        self.original_graph = graph
        self.config = config or HelixConfig.default()
        self.model_id = model_id
        self.optimizer = optimizer or self._build_optimizer(cache_path, graph_path)
        self.last_run_events: list[LangGraphNodeEvent] = []
        self._events_lock = threading.Lock()
        self._optimizer_lock = threading.Lock()
        self._active_run_id = str(uuid.uuid4())
        self.graph = self._wrap_graph(graph)

    def _build_optimizer(
        self,
        cache_path: str | None,
        graph_path: str | None,
    ) -> ExecutionOptimizer:
        embedding_provider = build_embedding_provider(
            self.config.embedding_backend.type,
            self.config.embedding_backend.model,
        )
        cache = CacheStore(cache_path or self.config.cache_db_path, self.config.cache, embedding_provider)
        graph = ComputationGraph(graph_path or self.config.graph_db_path)
        return ExecutionOptimizer(
            ContextDecomposer(SemanticHasher()),
            cache,
            graph,
            GraphReuser(graph),
            KVSimulator(self.config.model_specs),
            self.model_id,
            optimizations_enabled=True,
            semantic_review_mode=self.config.semantic_review.mode,
        )

    def _wrap_graph(self, graph: Any) -> Any:
        if not hasattr(graph, "nodes") or not hasattr(graph, "invoke"):
            raise TypeError("HelixLangGraphRunner expects a compiled LangGraph graph.")
        wrapped = copy.copy(graph)
        wrapped.nodes = dict(graph.nodes)
        for step_id, node in graph.nodes.items():
            if str(step_id).startswith("__"):
                continue
            bound = getattr(node, "bound", None)
            if bound is None:
                continue
            wrapped_bound = self._wrap_bound(step_id, bound)
            wrapped.nodes[step_id] = node.copy(update={"bound": wrapped_bound})
        return wrapped

    def _wrap_bound(self, step_id: str, bound: Any) -> Any:
        bound_cls = bound.__class__

        def invoke_with_helix(node_input: Any, config=None) -> Any:
            return self._invoke_node(step_id, bound, node_input, config)

        async def ainvoke_with_helix(node_input: Any, config=None) -> Any:
            return await self._ainvoke_node(step_id, bound, node_input, config)

        return bound_cls(
            invoke_with_helix,
            ainvoke_with_helix,
            name=getattr(bound, "name", step_id),
            tags=getattr(bound, "tags", None),
            trace=getattr(bound, "trace", False),
            recurse=getattr(bound, "recurse", True),
            explode_args=getattr(bound, "explode_args", False),
        )

    def _node_model_id(self, step_id: str) -> str:
        return f"{self.model_id}:{step_id}"

    def _workflow_for_node(self, step_id: str, node_input: Any) -> Workflow:
        model = self._node_model_id(step_id)
        return Workflow(
            workflow_id="langgraph_adapter",
            name="LangGraph Adapter",
            description="Synthetic one-node workflow used for Helix cache decisions.",
            default_model=model,
            steps=[
                WorkflowStep(
                    step_id=step_id,
                    step_type=WorkflowStepType.LLM_CALL,
                    model=model,
                    messages=[
                        {
                            "role": "user",
                            "content": stable_json(node_input),
                        }
                    ],
                )
            ],
        )

    def _current_run_id(self) -> str:
        return self._active_run_id

    def _append_event(self, event: LangGraphNodeEvent) -> None:
        with self._events_lock:
            self.last_run_events.append(event)

    def _invoke_node(self, step_id: str, bound: Any, node_input: Any, config: Any) -> Any:
        decision = self._plan_node(step_id, node_input)
        self._append_event(
            LangGraphNodeEvent(step_id, decision.decision, decision.cache_key, decision.reason)
        )
        if decision.decision == ExecutionDecisionType.CACHE_HIT and decision.cache_entry:
            return decision.cache_entry.response
        if decision.decision == ExecutionDecisionType.GRAPH_REUSE and decision.graph_node:
            return decision.graph_node.response

        started = time.perf_counter()
        output = ensure_cacheable_output(step_id, bound.invoke(node_input, config))
        latency_ms = (time.perf_counter() - started) * 1000
        with self._optimizer_lock:
            self.optimizer.record_execution(decision, output, latency_ms)
        return output

    async def _ainvoke_node(self, step_id: str, bound: Any, node_input: Any, config: Any) -> Any:
        decision = self._plan_node(step_id, node_input)
        self._append_event(
            LangGraphNodeEvent(step_id, decision.decision, decision.cache_key, decision.reason)
        )
        if decision.decision == ExecutionDecisionType.CACHE_HIT and decision.cache_entry:
            return decision.cache_entry.response
        if decision.decision == ExecutionDecisionType.GRAPH_REUSE and decision.graph_node:
            return decision.graph_node.response

        started = time.perf_counter()
        output = ensure_cacheable_output(step_id, await bound.ainvoke(node_input, config))
        latency_ms = (time.perf_counter() - started) * 1000
        with self._optimizer_lock:
            self.optimizer.record_execution(decision, output, latency_ms)
        return output

    def _plan_node(self, step_id: str, node_input: Any):
        workflow = self._workflow_for_node(step_id, node_input)
        with self._optimizer_lock:
            plan = self.optimizer.plan(workflow, self._current_run_id())
        return plan.decisions[0]

    def invoke(self, input_data: Any, **kwargs: Any) -> Any:
        """Invoke the wrapped LangGraph graph."""
        self.last_run_events = []
        self._active_run_id = str(uuid.uuid4())
        return self.graph.invoke(input_data, **kwargs)

    async def ainvoke(self, input_data: Any, **kwargs: Any) -> Any:
        """Invoke the wrapped LangGraph graph asynchronously."""
        self.last_run_events = []
        self._active_run_id = str(uuid.uuid4())
        return await self.graph.ainvoke(input_data, **kwargs)
