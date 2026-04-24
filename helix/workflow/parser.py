"""YAML workflow parser."""

from __future__ import annotations

from pathlib import Path

import yaml

from helix.exceptions import WorkflowValidationError
from helix.workflow.types import Workflow, WorkflowStep, WorkflowStepType


class WorkflowParser:
    """Parse and validate YAML workflows."""

    def parse_file(self, path: str) -> Workflow:
        """Parse a workflow YAML file."""
        return self.parse_yaml(Path(path).read_text())

    def parse_yaml(self, yaml_str: str) -> Workflow:
        """Parse a workflow from a YAML string."""
        data = yaml.safe_load(yaml_str) or {}
        steps = [
            WorkflowStep(
                step_id=item["step_id"],
                step_type=WorkflowStepType(item.get("step_type", "llm_call")),
                model=item.get("model") or data.get("default_model", "fake"),
                messages=item.get("messages", []),
                tool_name=item.get("tool_name"),
                tool_args=item.get("tool_args"),
                depends_on=list(item.get("depends_on", [])),
                cacheable=bool(item.get("cacheable", True)),
                tags=list(item.get("tags", [])),
            )
            for item in data.get("steps", [])
        ]
        workflow = Workflow(
            workflow_id=data["workflow_id"],
            name=data.get("name", data["workflow_id"]),
            description=data.get("description", ""),
            steps=steps,
            default_model=data.get("default_model", "fake"),
            metadata=data.get("metadata", {}),
        )
        errors = self.validate(workflow)
        if errors:
            raise WorkflowValidationError("; ".join(errors))
        return workflow

    def validate(self, workflow: Workflow) -> list[str]:
        """Return list of validation error strings. Empty = valid."""
        errors: list[str] = []
        if not workflow.steps:
            errors.append("workflow must contain at least one step")
        seen: set[str] = set()
        duplicates: set[str] = set()
        for step in workflow.steps:
            if step.step_id in seen:
                duplicates.add(step.step_id)
            seen.add(step.step_id)
        for step_id in sorted(duplicates):
            errors.append(f"duplicate step_id: {step_id}")
        all_ids = {step.step_id for step in workflow.steps}
        for step in workflow.steps:
            for dep in step.depends_on:
                if dep not in all_ids:
                    errors.append(f"step {step.step_id} depends on missing step {dep}")
        return errors

