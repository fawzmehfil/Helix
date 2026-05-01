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

from .llm_wrapper import LLMCallMetrics, capture_helix_metrics
from .utils import (
    TraceEntry,
    compute_summary,
    ensure_cacheable_output,
    ensure_langgraph_available,
    shallow_changed_fields,
    stable_json,
)


@dataclass(frozen=True)
class LangGraphNodeEvent:
    """Execution decision for one LangGraph node."""

    step_id: str
    decision: ExecutionDecisionType
    cache_key: str | None
    reason: str


@dataclass
class NodeMetrics:
    """Runtime LLM metrics collected for one LangGraph node."""

    calls_made: int = 0
    calls_avoided: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0

    def record_call(self, metrics: LLMCallMetrics) -> None:
        """Accumulate one measured LLM call."""
        self.calls_made += metrics.calls_made
        self.input_tokens += metrics.input_tokens
        self.output_tokens += metrics.output_tokens
        self.total_tokens += metrics.total_tokens
        self.cost_usd += metrics.cost_usd
        self.latency_ms += metrics.latency_ms

    def record_avoided(self) -> None:
        """Record one cached node execution."""
        self.calls_avoided += 1

    def to_dict(self) -> dict[str, int | float]:
        """Return JSON-serializable metrics."""
        return {
            "calls_made": self.calls_made,
            "calls_avoided": self.calls_avoided,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "tokens": self.total_tokens,
            "cost_usd": self.cost_usd,
            "latency_ms": self.latency_ms,
        }


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
        self._trace: list[TraceEntry] = []
        self._metrics: dict[str, NodeMetrics] = {}
        self._previous_inputs: dict[str, Any] = {}
        self._events_lock = threading.Lock()
        self._metrics_lock = threading.Lock()
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

    def _trace_decision(self, step_id: str, node_input: Any, decision) -> TraceEntry:
        previous_input = self._previous_inputs.get(step_id)
        if decision.decision in {ExecutionDecisionType.CACHE_HIT, ExecutionDecisionType.GRAPH_REUSE}:
            trace_decision = "cache_hit"
            reason = "input unchanged"
        else:
            trace_decision = "execute"
            changed = shallow_changed_fields(previous_input, node_input)
            if changed:
                reason = f"input changed: {', '.join(changed)}"
            elif previous_input is not None:
                reason = "input changed"
            else:
                reason = "no cache entry"
        input_hash = (decision.cache_key or "")[:12]
        return TraceEntry(step_id, trace_decision, reason, input_hash, [])

    def _append_trace(self, entry: TraceEntry) -> None:
        with self._events_lock:
            self._trace.append(entry)

    def _node_metrics(self, step_id: str) -> NodeMetrics:
        return self._metrics.setdefault(step_id, NodeMetrics())

    def _record_call_metrics(self, step_id: str, metrics: LLMCallMetrics) -> None:
        with self._metrics_lock:
            self._node_metrics(step_id).record_call(metrics)

    def _record_avoided_call(self, step_id: str) -> None:
        with self._metrics_lock:
            self._node_metrics(step_id).record_avoided()

    def _remember_input(self, step_id: str, node_input: Any) -> None:
        self._previous_inputs[step_id] = copy.deepcopy(node_input)

    def _invoke_node(self, step_id: str, bound: Any, node_input: Any, config: Any) -> Any:
        decision = self._plan_node(step_id, node_input)
        self._append_event(
            LangGraphNodeEvent(step_id, decision.decision, decision.cache_key, decision.reason)
        )
        self._append_trace(self._trace_decision(step_id, node_input, decision))
        if decision.decision == ExecutionDecisionType.CACHE_HIT and decision.cache_entry:
            self._record_avoided_call(step_id)
            self._remember_input(step_id, node_input)
            return decision.cache_entry.response
        if decision.decision == ExecutionDecisionType.GRAPH_REUSE and decision.graph_node:
            self._record_avoided_call(step_id)
            self._remember_input(step_id, node_input)
            return decision.graph_node.response

        started = time.perf_counter()
        with capture_helix_metrics(lambda metrics: self._record_call_metrics(step_id, metrics)):
            output = ensure_cacheable_output(step_id, bound.invoke(node_input, config))
        latency_ms = (time.perf_counter() - started) * 1000
        with self._optimizer_lock:
            self.optimizer.record_execution(decision, output, latency_ms)
        self._remember_input(step_id, node_input)
        return output

    async def _ainvoke_node(self, step_id: str, bound: Any, node_input: Any, config: Any) -> Any:
        decision = self._plan_node(step_id, node_input)
        self._append_event(
            LangGraphNodeEvent(step_id, decision.decision, decision.cache_key, decision.reason)
        )
        self._append_trace(self._trace_decision(step_id, node_input, decision))
        if decision.decision == ExecutionDecisionType.CACHE_HIT and decision.cache_entry:
            self._record_avoided_call(step_id)
            self._remember_input(step_id, node_input)
            return decision.cache_entry.response
        if decision.decision == ExecutionDecisionType.GRAPH_REUSE and decision.graph_node:
            self._record_avoided_call(step_id)
            self._remember_input(step_id, node_input)
            return decision.graph_node.response

        started = time.perf_counter()
        with capture_helix_metrics(lambda metrics: self._record_call_metrics(step_id, metrics)):
            output = ensure_cacheable_output(step_id, await bound.ainvoke(node_input, config))
        latency_ms = (time.perf_counter() - started) * 1000
        with self._optimizer_lock:
            self.optimizer.record_execution(decision, output, latency_ms)
        self._remember_input(step_id, node_input)
        return output

    def _plan_node(self, step_id: str, node_input: Any):
        workflow = self._workflow_for_node(step_id, node_input)
        with self._optimizer_lock:
            plan = self.optimizer.plan(workflow, self._current_run_id())
        return plan.decisions[0]

    def invoke(self, input_data: Any, **kwargs: Any) -> Any:
        """Invoke the wrapped LangGraph graph."""
        self.last_run_events = []
        self._trace = []
        self._metrics = {}
        self._active_run_id = str(uuid.uuid4())
        return self.graph.invoke(input_data, **kwargs)

    async def ainvoke(self, input_data: Any, **kwargs: Any) -> Any:
        """Invoke the wrapped LangGraph graph asynchronously."""
        self.last_run_events = []
        self._trace = []
        self._metrics = {}
        self._active_run_id = str(uuid.uuid4())
        return await self.graph.ainvoke(input_data, **kwargs)

    def get_trace(self) -> list[TraceEntry]:
        """Return the most recent LangGraph run trace."""
        return list(self._trace)

    def get_trace_json(self) -> dict[str, Any]:
        """Return the most recent trace and summary as JSON-serializable data."""
        trace = self.get_trace()
        return {
            "trace": [entry.to_dict() for entry in trace],
            "summary": compute_summary(trace),
            "metrics": self.get_metrics_summary(),
        }

    def get_node_metrics(self) -> dict[str, dict[str, int | float]]:
        """Return per-node runtime metrics for the most recent run."""
        with self._metrics_lock:
            return {step_id: metrics.to_dict() for step_id, metrics in self._metrics.items()}

    def get_metrics_summary(self) -> dict[str, int | float]:
        """Return aggregate runtime metrics for the most recent run."""
        with self._metrics_lock:
            node_metrics = list(self._metrics.values())
        calls_made = sum(metrics.calls_made for metrics in node_metrics)
        calls_avoided = sum(metrics.calls_avoided for metrics in node_metrics)
        input_tokens = sum(metrics.input_tokens for metrics in node_metrics)
        output_tokens = sum(metrics.output_tokens for metrics in node_metrics)
        total_tokens = sum(metrics.total_tokens for metrics in node_metrics)
        cost_usd = sum(metrics.cost_usd for metrics in node_metrics)
        latency_ms = sum(metrics.latency_ms for metrics in node_metrics)
        trace_summary = compute_summary(self.get_trace())
        return {
            "total_calls": calls_made,
            "calls_made": calls_made,
            "calls_avoided": calls_avoided,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "tokens": total_tokens,
            "total_cost": cost_usd,
            "cost_usd": cost_usd,
            "total_latency": latency_ms,
            "latency_ms": latency_ms,
            "reuse_rate": trace_summary["reuse_rate"],
        }
