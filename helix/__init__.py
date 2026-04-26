"""Helix package exports."""

from __future__ import annotations

from helix.config import HelixConfig

__all__ = ["HelixConfig", "WorkflowRunner", "BenchmarkRunner", "run_workflow"]


def run_workflow(
    workflow_path: str,
    input_data: dict[str, str] | None = None,
    backend: str = "fake",
):
    """Run a workflow through the optimized runner and return a RunResult."""
    from helix.cli.commands._common import build_runner
    from helix.workflow import WorkflowParser

    workflow = WorkflowParser().parse_file(workflow_path)
    runner = build_runner(backend, baseline=False)
    return runner.run(workflow, input_data or {})


def __getattr__(name: str) -> object:
    """Lazily export heavier classes without creating import cycles."""
    if name == "WorkflowRunner":
        from helix.workflow.runner import WorkflowRunner

        return WorkflowRunner
    if name == "BenchmarkRunner":
        from helix.benchmark_engine.runner import BenchmarkRunner

        return BenchmarkRunner
    raise AttributeError(name)
