"""Convenience helpers for LangGraph-first Helix usage."""

from __future__ import annotations

from typing import Any, Sequence

from helix.config import HelixConfig
from helix.execution_optimizer import ExecutionOptimizer

from .runner import HelixLangGraphRunner
from .utils import ensure_langgraph_available


def _coerce_compiled_graph(graph: Any) -> Any:
    """Return a compiled LangGraph graph, compiling builder-like objects when safe."""
    if hasattr(graph, "nodes") and hasattr(graph, "invoke"):
        return graph
    if hasattr(graph, "compile"):
        return graph.compile()
    return graph


def helix_langgraph(
    graph: Any,
    *,
    config: HelixConfig | None = None,
    optimizer: ExecutionOptimizer | None = None,
    cache_path: str | None = None,
    graph_path: str | None = None,
    model_id: str = "langgraph",
    node_inputs: dict[str, Sequence[str]] | None = None,
) -> HelixLangGraphRunner:
    """Create a Helix runner for a compiled or builder-like LangGraph graph."""
    ensure_langgraph_available()
    return HelixLangGraphRunner(
        _coerce_compiled_graph(graph),
        config=config,
        optimizer=optimizer,
        cache_path=cache_path,
        graph_path=graph_path,
        model_id=model_id,
        node_inputs=node_inputs,
    )
