"""Cache commands."""

from __future__ import annotations

import click
from rich.table import Table

from helix.cache_engine import CacheStore
from helix.cli.commands._common import console
from helix.config import HelixConfig


@click.group("cache")
def cache_group() -> None:
    """Inspect and clear the Helix cache."""


@cache_group.command("clear")
def cache_clear() -> None:
    """Clear cache entries."""
    cfg = HelixConfig.default()
    count = CacheStore(cfg.cache_db_path, cfg.cache).clear()
    console.print(f"Cleared {count} cache entries.")


@cache_group.command("show")
def cache_show() -> None:
    """Show cache entries."""
    cfg = HelixConfig.default()
    entries = CacheStore(cfg.cache_db_path, cfg.cache).list_entries(20)
    table = Table(title="Helix cache")
    table.add_column("Key")
    table.add_column("Step")
    table.add_column("Hits")
    table.add_column("Created")
    for entry in entries:
        table.add_row(entry.key[:12], entry.step_id, str(entry.hit_count), entry.created_at.isoformat())
    console.print(table)

