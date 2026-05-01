"""Utilities for adapting LangGraph node inputs to Helix cache inputs."""

from __future__ import annotations

import importlib.util
import json
from typing import Any


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
