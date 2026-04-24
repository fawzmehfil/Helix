"""Workflow dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from helix.execution_optimizer.types import ExecutionDecisionType, OptimizationPlan
from helix.kv_simulator.types import KVReuseEstimate


class WorkflowStepType(Enum):
    """Supported workflow step types."""

    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    BRANCH = "branch"


@dataclass
class WorkflowStep:
    """One ordered step in a workflow."""

    step_id: str
    step_type: WorkflowStepType
    model: str
    messages: list[dict]
    tool_name: Optional[str] = None
    tool_args: Optional[dict] = None
    depends_on: list[str] = field(default_factory=list)
    cacheable: bool = True
    tags: list[str] = field(default_factory=list)
    input_projection: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    output_format: Optional[str] = None
    compact: bool = False
    max_output_tokens: Optional[int] = None
    semantic_reuse: bool = False
    semantic_threshold: float = 0.92
    required_fields: list[str] = field(default_factory=list)


@dataclass
class Workflow:
    """A Helix YAML workflow."""

    workflow_id: str
    name: str
    description: str
    steps: list[WorkflowStep]
    default_model: str = "fake"
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class StepResult:
    """Result for one workflow step."""

    step_id: str
    decision: ExecutionDecisionType
    response: dict
    input_tokens: int
    output_tokens: int
    latency_ms: float
    kv_estimate: Optional[KVReuseEstimate]
    cache_hit: bool
    graph_reuse: bool
    model: str = "unknown"
    estimated_cost_usd: float = 0.0
    call_count: int = 0
    raw_input_tokens: int = 0
    minimized_input_tokens: int = 0
    tokens_saved_by_minimization: int = 0
    optimization_overhead_tokens: int = 0
    net_token_change: int = 0
    raw_messages: list[dict[str, Any]] = field(default_factory=list)
    minimized_messages: list[dict[str, Any]] = field(default_factory=list)
    repair_attempted: bool = False
    repair_successful: bool = False
    structured_output_failed: bool = False
    semantic_cache_hit: bool = False
    semantic_reuse_applied: bool = False
    similarity_score: float = 0.0


@dataclass
class RunResult:
    """Result for a workflow run."""

    run_id: str
    workflow_id: str
    step_results: list[StepResult]
    total_latency_ms: float
    total_input_tokens: int
    total_output_tokens: int
    optimization_plan: Optional[OptimizationPlan]
    baseline_mode: bool
