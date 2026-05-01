"""Utilities for adapting LangGraph node inputs to Helix cache inputs."""

from __future__ import annotations

import importlib.util
import json
import copy
from dataclasses import asdict, dataclass
from typing import Any, Sequence


@dataclass(frozen=True)
class TraceEntry:
    """One Helix decision for a LangGraph node execution."""

    step_id: str
    decision: str
    reason: str
    input_hash: str
    dependency_info: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return asdict(self)


def ensure_langgraph_available() -> None:
    """Raise a clear error when LangGraph is not installed."""
    if importlib.util.find_spec("langgraph") is None:
        raise ImportError(
            "LangGraph support requires the optional 'langgraph' package. "
            "Install it with `pip install langgraph`."
        )


def stable_json(value: Any) -> str:
    """Return a deterministic JSON representation for cache input hashing."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def shallow_changed_fields(previous: Any, current: Any) -> list[str]:
    """Return shallow dict keys whose values changed, were added, or were removed."""
    if not isinstance(previous, dict) or not isinstance(current, dict):
        return []
    keys = set(previous) | set(current)
    return sorted(key for key in keys if previous.get(key) != current.get(key))


def project_node_input(node_input: Any, fields: Sequence[str] | None) -> Any:
    """Return the cache input for a LangGraph node without mutating original state."""
    if fields is None:
        return node_input
    source = node_input if isinstance(node_input, dict) else {}
    return {field: copy_value(source.get(field)) for field in fields}


def copy_value(value: Any) -> Any:
    """Copy projected values so later LangGraph mutations do not affect trace diffs."""
    try:
        return copy.deepcopy(value)
    except Exception:
        return value


def compute_summary(trace: list[TraceEntry]) -> dict[str, float | int]:
    """Compute a lightweight LangGraph run summary from trace entries."""
    total_nodes = len(trace)
    nodes_reused = sum(1 for entry in trace if entry.decision == "cache_hit")
    nodes_executed = sum(1 for entry in trace if entry.decision == "execute")
    return {
        "total_nodes": total_nodes,
        "nodes_reused": nodes_reused,
        "nodes_executed": nodes_executed,
        "reuse_rate": nodes_reused / total_nodes if total_nodes else 0.0,
        "estimated_calls_avoided": nodes_reused,
    }


def ensure_cacheable_output(step_id: str, output: Any) -> dict[str, Any]:
    """Validate that a LangGraph node output can be stored by Helix's cache."""
    if not isinstance(output, dict):
        raise TypeError(
            f"LangGraph node '{step_id}' returned {type(output).__name__}; "
            "Helix LangGraph caching currently supports JSON-serializable dict outputs."
        )
    try:
        json.dumps(output, sort_keys=True)
    except TypeError as exc:
        raise TypeError(
            f"LangGraph node '{step_id}' returned a dict that is not JSON-serializable."
        ) from exc
    return output
