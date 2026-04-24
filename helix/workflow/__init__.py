"""Workflow exports."""

from __future__ import annotations

from helix.workflow.parser import WorkflowParser
from helix.workflow.types import RunResult, StepResult, Workflow, WorkflowStep, WorkflowStepType

__all__ = [
    "WorkflowStepType",
    "WorkflowStep",
    "Workflow",
    "WorkflowParser",
    "WorkflowRunner",
    "RunResult",
    "StepResult",
]


def __getattr__(name: str) -> object:
    """Lazily export WorkflowRunner to avoid benchmark import cycles."""
    if name == "WorkflowRunner":
        from helix.workflow.runner import WorkflowRunner

        return WorkflowRunner
    raise AttributeError(name)
