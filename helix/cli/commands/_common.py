"""Common CLI construction helpers."""

from __future__ import annotations

from rich.console import Console

from helix.api_clients import EchoToolClient, LLMClientFactory
from helix.benchmark_engine import BenchmarkCollector
from helix.cache_engine import CacheStore
from helix.config import HelixConfig
from helix.context_engine import ContextDecomposer, SemanticHasher
from helix.execution_optimizer import ExecutionOptimizer
from helix.graph_engine import ComputationGraph, GraphReuser
from helix.kv_simulator import KVSimulator
from helix.workflow import WorkflowRunner

console = Console()


def parse_inputs(items: tuple[str, ...]) -> dict[str, str]:
    """Parse key=value CLI inputs."""
    parsed: dict[str, str] = {}
    for item in items:
        if "=" in item:
            key, value = item.split("=", 1)
            parsed[key] = value
    return parsed


def build_runner(
    backend: str,
    baseline: bool = False,
    cache_path: str | None = None,
    graph_path: str | None = None,
    model: str | None = None,
    require_available: bool = False,
) -> WorkflowRunner:
    """Construct a workflow runner with default local dependencies."""
    cfg = HelixConfig.default()
    client = LLMClientFactory.create(
        backend or cfg.llm_backend,
        model or cfg.model,
        require_available=require_available,
    )
    cache = CacheStore(cache_path or cfg.cache_db_path, cfg.cache)
    graph = ComputationGraph(graph_path or cfg.graph_db_path)
    hasher = SemanticHasher()
    decomposer = ContextDecomposer(hasher)
    kv = KVSimulator(cfg.model_specs)
    optimizer = ExecutionOptimizer(
        decomposer,
        cache,
        graph,
        GraphReuser(graph),
        kv,
        client.model_id,
        optimizations_enabled=not baseline,
    )
    return WorkflowRunner(optimizer, client, EchoToolClient(), BenchmarkCollector(), baseline)
