"""Shared Helix test fixtures."""

from __future__ import annotations

import os

import pytest


@pytest.fixture
def cache_db_path(tmp_path):
    """Return a temporary cache DB path."""
    return str(tmp_path / "cache.db")


@pytest.fixture
def graph_db_path(tmp_path):
    """Return a temporary graph DB path."""
    return str(tmp_path / "graph.db")


@pytest.fixture(autouse=True)
def isolated_helix_paths(tmp_path, monkeypatch):
    """Keep tests away from the user's Helix state."""
    monkeypatch.setenv("HELIX_CACHE_PATH", str(tmp_path / "cache.db"))
    monkeypatch.setenv("HELIX_GRAPH_PATH", str(tmp_path / "graph.db"))
    monkeypatch.setenv("HELIX_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("HELIX_LLM_BACKEND", "fake")
    yield
    os.environ.pop("HELIX_CACHE_PATH", None)
    os.environ.pop("HELIX_GRAPH_PATH", None)
