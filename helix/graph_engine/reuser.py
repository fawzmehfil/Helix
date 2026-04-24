"""Graph reuse lookup."""

from __future__ import annotations

from typing import Optional

from helix.context_engine.types import ContextSnapshot
from helix.graph_engine.graph import ComputationGraph
from helix.graph_engine.types import GraphNode


class GraphReuser:
    """Find reusable graph nodes."""

    def __init__(self, graph: ComputationGraph) -> None:
        """Create a graph reuser."""
        self.graph = graph

    def find_reusable_node(self, snapshot: ContextSnapshot, model_id: str) -> Optional[GraphNode]:
        """Look up graph for a node whose input_hash matches snapshot.composite_hash."""
        return self.graph.find_node(snapshot.composite_hash, model_id)

