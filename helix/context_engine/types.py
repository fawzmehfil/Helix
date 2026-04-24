"""Context dataclasses for Helix."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class ContextBlockType(Enum):
    """Typed context block categories."""

    SYSTEM = auto()
    STATIC_PREFIX = auto()
    DYNAMIC_CONTENT = auto()
    HISTORY = auto()
    TOOL_RESULT = auto()
    UNKNOWN = auto()


@dataclass(frozen=True)
class ContextBlock:
    """A hashable block of prompt context."""

    block_type: ContextBlockType
    content: str
    block_hash: str
    token_estimate: int
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class ContextSnapshot:
    """Context blocks and aggregate metadata for one step."""

    step_id: str
    run_id: str
    blocks: list[ContextBlock]
    total_tokens: int
    composite_hash: str


@dataclass
class ContextDiff:
    """Difference between two context snapshots."""

    added_blocks: list[ContextBlock]
    removed_blocks: list[ContextBlock]
    unchanged_blocks: list[ContextBlock]
    changed_fraction: float

