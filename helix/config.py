"""Helix configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from helix.cache_engine.types import CachePolicy
from helix.kv_simulator.types import ModelSpec


@dataclass
class HelixConfig:
    """Runtime configuration for Helix."""

    llm_backend: str = "fake"
    model: Optional[str] = None
    cache: CachePolicy = field(default_factory=CachePolicy)
    graph_enabled: bool = True
    kv_simulation_enabled: bool = True
    cache_db_path: str = "~/.helix/cache.db"
    graph_db_path: str = "~/.helix/graph.db"
    runs_dir: str = "~/.helix/runs/"
    model_specs: dict[str, ModelSpec] = field(default_factory=dict)
    cost_table: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str) -> "HelixConfig":
        """Load configuration from YAML."""
        data = yaml.safe_load(Path(path).expanduser().read_text()) or {}
        cfg = cls.default()
        cfg.llm_backend = data.get("llm_backend", cfg.llm_backend)
        cfg.model = data.get("model", cfg.model)
        cache_data = data.get("cache", {})
        cfg.cache = CachePolicy(
            enabled=cache_data.get("enabled", cfg.cache.enabled),
            ttl_seconds=cache_data.get("ttl_seconds", cfg.cache.ttl_seconds),
            max_entries=cache_data.get("max_entries", cfg.cache.max_entries),
            eviction=cache_data.get("eviction", cfg.cache.eviction),
        )
        cfg.graph_enabled = data.get("graph", {}).get("enabled", cfg.graph_enabled)
        cfg.kv_simulation_enabled = data.get("kv_simulation", {}).get("enabled", cfg.kv_simulation_enabled)
        specs = data.get("kv_simulation", {}).get("model_specs", {})
        for model_id, item in specs.items():
            cfg.model_specs[model_id] = ModelSpec(
                model_id=model_id,
                tokens_per_second=float(item.get("tokens_per_second", 60)),
                cache_hit_multiplier=float(item.get("cache_hit_multiplier", 0.1)),
                cost_per_1k_input_tokens=float(item.get("cost_per_1k_input_tokens", 0.0)),
                cost_per_1k_output_tokens=float(item.get("cost_per_1k_output_tokens", 0.0)),
            )
        cfg.cost_table.update(data.get("benchmark", {}).get("cost_per_1k_tokens", {}))
        return cfg

    @classmethod
    def default(cls) -> "HelixConfig":
        """Return default Helix configuration with environment overrides."""
        cfg = cls()
        cfg.llm_backend = os.environ.get("HELIX_LLM_BACKEND", cfg.llm_backend)
        cfg.cache_db_path = os.environ.get("HELIX_CACHE_PATH", cfg.cache_db_path)
        cfg.graph_db_path = os.environ.get("HELIX_GRAPH_PATH", cfg.graph_db_path)
        cfg.runs_dir = os.environ.get("HELIX_RUNS_DIR", cfg.runs_dir)
        cfg.model_specs = {
            "fake": ModelSpec("fake", 60.0, 0.1, 0.0, 0.0),
            "gpt-4o": ModelSpec("gpt-4o", 60.0, 0.1, 0.005, 0.005),
            "claude-3-5-sonnet": ModelSpec("claude-3-5-sonnet", 80.0, 0.1, 0.003, 0.003),
        }
        cfg.cost_table = {"fake": 0.0, "gpt-4o": 0.005, "claude-3-5-sonnet": 0.003}
        return cfg
