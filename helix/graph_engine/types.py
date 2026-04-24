"""Graph engine types."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GraphNode:
    """A persisted computation graph node."""

    node_id: str
    step_id: str
    run_id: str
    input_hash: str
    output_hash: str
    response: dict
    input_tokens: int
    output_tokens: int
    latency_ms: float
    model_id: str
    created_at: dt.datetime
    parent_node_ids: list[str] = field(default_factory=list)
    reuse_source_id: Optional[str] = None

