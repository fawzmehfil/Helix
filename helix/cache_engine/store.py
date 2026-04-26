"""SQLite-backed cache store."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Optional

from helix.cache_engine.types import CacheEntry, CacheKey, CachePolicy, SemanticCacheMatch
from helix.embeddings import CachedEmbeddingProvider, build_embedding_provider, cosine_similarity


class CacheStore:
    """SQLite-backed cache storage."""

    def __init__(
        self,
        db_path: str,
        policy: CachePolicy,
        embedding_provider: CachedEmbeddingProvider | None = None,
    ) -> None:
        """Initialize a cache database."""
        self.db_path = str(Path(db_path).expanduser())
        self.policy = policy
        self.embedding_provider = embedding_provider or build_embedding_provider("local")
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

    def put_semantic(
        self,
        key: CacheKey,
        entry: CacheEntry,
        step_id: str,
        model_id: str,
        minimized_input: str,
    ) -> None:
        """Persist semantic-reuse metadata for an executed step."""
        if not self.policy.enabled:
            return
        embedding = self.embedding_provider.embed(minimized_input)
        semantic_id = hashlib.sha256(f"{key.key}|{minimized_input}".encode("utf-8")).hexdigest()
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO semantic_cache_entries VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    semantic_id,
                    key.key,
                    step_id,
                    model_id,
                    minimized_input,
                    json.dumps(embedding, sort_keys=True),
                    json.dumps(entry.response, sort_keys=True),
                    entry.input_tokens,
                    entry.output_tokens,
                    entry.latency_ms,
                    entry.created_at.isoformat(),
                ),
            )

    def find_semantic(
        self,
        step_id: str,
        model_id: str,
        minimized_input: str,
        threshold: float,
    ) -> Optional[SemanticCacheMatch]:
        """Return the nearest semantic cache entry above threshold."""
        if not self.policy.enabled:
            return None
        embedded = self.embedding_provider.embed_measured(minimized_input)
        query_embedding = embedded.vector
        best_row = None
        best_score = 0.0
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT cache_key,step_id,response,input_tokens,output_tokens,latency_ms,"
                "created_at,embedding,minimized_input FROM semantic_cache_entries WHERE step_id=? AND model_id=?",
                (step_id, model_id),
            ).fetchall()
            for row in rows:
                score = cosine_similarity(query_embedding, json.loads(row[7]))
                if score > best_score:
                    best_score = score
                    best_row = row
            if best_row is None or best_score < threshold:
                return None
            conn.execute(
                "UPDATE cache_entries SET hit_count=hit_count+1 WHERE key=?",
                (best_row[0],),
            )
        entry = CacheEntry(
            key=best_row[0],
            step_id=best_row[1],
            run_id="semantic-reuse",
            response=json.loads(best_row[2]),
            input_tokens=best_row[3],
            output_tokens=best_row[4],
            latency_ms=best_row[5],
            created_at=self._parse_datetime(best_row[6]),
            expires_at=None,
            hit_count=1,
        )
        return SemanticCacheMatch(
            entry=entry,
            similarity=best_score,
            previous_input=best_row[8],
            embedding_latency_ms=embedded.latency_ms,
            embedding_calls=embedded.calls,
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
            conn.execute("DELETE FROM semantic_cache_entries")
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
