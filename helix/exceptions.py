"""Exception hierarchy for Helix."""

from __future__ import annotations


class HelixError(Exception):
    """Base exception for all Helix errors."""


class WorkflowValidationError(HelixError):
    """Raised when a workflow is invalid."""


class CacheError(HelixError):
    """Raised when cache operations fail."""


class GraphError(HelixError):
    """Raised when graph operations fail."""


class LLMClientError(HelixError):
    """Raised when an LLM client fails."""


class ConfigError(HelixError):
    """Raised when configuration is invalid."""

