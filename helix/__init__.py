"""Helix package exports."""

from __future__ import annotations

from helix.config import HelixConfig

__all__ = ["HelixConfig", "WorkflowRunner", "BenchmarkRunner"]


def __getattr__(name: str) -> object:
    """Lazily export heavier classes without creating import cycles."""
    if name == "WorkflowRunner":
        from helix.workflow.runner import WorkflowRunner

        return WorkflowRunner
    if name == "BenchmarkRunner":
        from helix.benchmark_engine.runner import BenchmarkRunner

        return BenchmarkRunner
    raise AttributeError(name)
