"""Workflow dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

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

