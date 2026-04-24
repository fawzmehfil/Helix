"""SQLite-backed cache store."""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
from pathlib import Path
from typing import Optional

from helix.cache_engine.types import CacheEntry, CacheKey, CachePolicy


class CacheStore:
    """SQLite-backed cache storage."""

    def __init__(self, db_path: str, policy: CachePolicy) -> None:
        """Initialize a cache database."""
        self.db_path = str(Path(db_path).expanduser())
        self.policy = policy
        self._miss_count = 0
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(Path(__file__).with_name("schema.sql").read_text())

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _row_to_entry(self, row: tuple) -> CacheEntry:
        return CacheEntry(
            key=row[0],
            step_id=row[1],
            run_id=row[2],
            response=json.loads(row[3]),
            input_tokens=row[4],
            output_tokens=row[5],
            latency_ms=row[6],
            created_at=self._parse_datetime(row[7]),
            expires_at=self._parse_datetime(row[8]) if row[8] else None,
            hit_count=row[9],
        )

    def _parse_datetime(self, value: str) -> dt.datetime:
        parsed = dt.datetime.fromisoformat(value)
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=dt.UTC)

    def get(self, key: CacheKey) -> Optional[CacheEntry]:
        """Return entry if present and not expired. Increment hit_count."""
        if not self.policy.enabled:
            self._miss_count += 1
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT key,step_id,run_id,response,input_tokens,output_tokens,latency_ms,"
                "created_at,expires_at,hit_count FROM cache_entries WHERE key=?",
                (key.key,),
            ).fetchone()
            if not row:
                self._miss_count += 1
                return None
            entry = self._row_to_entry(row)
            if entry.expires_at and entry.expires_at <= dt.datetime.now(dt.UTC):
                conn.execute("DELETE FROM cache_entries WHERE key=?", (key.key,))
                self._miss_count += 1
                return None
            conn.execute("UPDATE cache_entries SET hit_count=hit_count+1 WHERE key=?", (key.key,))
            entry.hit_count += 1
            return entry

    def put(self, key: CacheKey, entry: CacheEntry) -> None:
        """Insert or replace. Enforce max_entries via eviction."""
        if not self.policy.enabled:
            return
        block_hashes = json.dumps([block.block_hash for block in key.blocks])
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache_entries VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    key.key,
                    entry.step_id,
                    entry.run_id,
                    json.dumps(entry.response, sort_keys=True),
                    entry.input_tokens,
                    entry.output_tokens,
                    entry.latency_ms,
                    entry.created_at.isoformat(),
                    entry.expires_at.isoformat() if entry.expires_at else None,
                    entry.hit_count,
                    block_hashes,
                ),
            )
            overflow = conn.execute("SELECT COUNT(*) FROM cache_entries").fetchone()[0] - self.policy.max_entries
            if overflow > 0:
                conn.execute(
                    "DELETE FROM cache_entries WHERE key IN (SELECT key FROM cache_entries "
                    "ORDER BY hit_count ASC, created_at ASC LIMIT ?)",
                    (overflow,),
                )

    def invalidate(self, key: CacheKey) -> bool:
        """Remove a single entry. Return True if it existed."""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM cache_entries WHERE key=?", (key.key,))
            return cur.rowcount > 0

    def invalidate_by_block_hash(self, block_hash: str) -> int:
        """Remove all entries whose composite key includes block_hash. Return count."""
        removed = 0
        with self._connect() as conn:
            rows = conn.execute("SELECT key, block_hashes FROM cache_entries").fetchall()
            for key, hashes_json in rows:
                if block_hash in json.loads(hashes_json):
                    conn.execute("DELETE FROM cache_entries WHERE key=?", (key,))
                    removed += 1
        return removed

    def clear(self) -> int:
        """Delete all entries. Return count deleted."""
        with self._connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM cache_entries").fetchone()[0]
            conn.execute("DELETE FROM cache_entries")
            return int(count)

    def list_entries(self, limit: int = 100) -> list[CacheEntry]:
        """List cache entries ordered by newest first."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT key,step_id,run_id,response,input_tokens,output_tokens,latency_ms,"
                "created_at,expires_at,hit_count FROM cache_entries ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def stats(self) -> dict[str, int]:
        """Return {'total_entries': N, 'hit_count': N, 'miss_count': N}."""
        with self._connect() as conn:
            total, hits = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(hit_count),0) FROM cache_entries"
            ).fetchone()
        return {"total_entries": int(total), "hit_count": int(hits), "miss_count": self._miss_count}
