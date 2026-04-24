"""Execution optimizer types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from helix.cache_engine.types import CacheEntry
from helix.graph_engine.types import GraphNode
from helix.kv_simulator.types import KVReuseEstimate


class ExecutionDecisionType(Enum):
    """Decision for a workflow step."""

    EXECUTE = "execute"
    CACHE_HIT = "cache_hit"
    GRAPH_REUSE = "graph_reuse"
    SKIP = "skip"


@dataclass
class ExecutionDecision:
    """Optimizer decision for one step."""

    step_id: str
    decision: ExecutionDecisionType
    cache_entry: Optional[CacheEntry] = None
    graph_node: Optional[GraphNode] = None
    kv_estimate: Optional[KVReuseEstimate] = None
    reason: str = ""


@dataclass
class OptimizationPlan:
    """Execution decisions for a workflow run."""

    run_id: str
    workflow_id: str
    decisions: list[ExecutionDecision]
    estimated_total_time_saved_ms: float
    estimated_total_cost_saved_usd: float

