"""SQLite-backed computation graph."""

from __future__ import annotations

import json
import sqlite3
import datetime as dt
from pathlib import Path
from typing import Optional

from helix.graph_engine.types import GraphNode


class ComputationGraph:
    """Append-only SQLite computation DAG."""

    def __init__(self, db_path: str) -> None:
        """Initialize a graph database."""
        self.db_path = str(Path(db_path).expanduser())
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(Path(__file__).with_name("schema.sql").read_text())

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _row_to_node(self, row: tuple) -> GraphNode:
        return GraphNode(
            node_id=row[0],
            step_id=row[1],
            run_id=row[2],
            input_hash=row[3],
            output_hash=row[4],
            response=json.loads(row[5]),
            input_tokens=row[6],
            output_tokens=row[7],
            latency_ms=row[8],
            model_id=row[9],
            created_at=dt.datetime.fromisoformat(row[10]),
            reuse_source_id=row[11],
            parent_node_ids=json.loads(row[12]),
        )

    def add_node(self, node: GraphNode) -> None:
        """Add a new graph node without mutating existing nodes."""
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO graph_nodes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    node.node_id,
                    node.step_id,
                    node.run_id,
                    node.input_hash,
                    node.output_hash,
                    json.dumps(node.response, sort_keys=True),
                    node.input_tokens,
                    node.output_tokens,
                    node.latency_ms,
                    node.model_id,
                    node.created_at.isoformat(),
                    node.reuse_source_id,
                    json.dumps(node.parent_node_ids),
                ),
            )

    def find_node(self, input_hash: str, model_id: str) -> Optional[GraphNode]:
        """Return the most recent node with matching input_hash and model_id."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM graph_nodes WHERE input_hash=? AND model_id=? "
                "ORDER BY created_at DESC LIMIT 1",
                (input_hash, model_id),
            ).fetchone()
        return self._row_to_node(row) if row else None

    def find_subtree(self, root_input_hash: str, step_sequence: list[str]) -> list[GraphNode]:
        """Return a matching node sequence if all requested steps are stored."""
        nodes: list[GraphNode] = []
        with self._connect() as conn:
            first = conn.execute(
                "SELECT * FROM graph_nodes WHERE input_hash=? AND step_id=? ORDER BY created_at DESC LIMIT 1",
                (root_input_hash, step_sequence[0] if step_sequence else ""),
            ).fetchone()
            if not first:
                return []
            nodes.append(self._row_to_node(first))
            for step_id in step_sequence[1:]:
                row = conn.execute(
                    "SELECT * FROM graph_nodes WHERE step_id=? ORDER BY created_at DESC LIMIT 1",
                    (step_id,),
                ).fetchone()
                if not row:
                    return []
                nodes.append(self._row_to_node(row))
        return nodes

    def get_run_nodes(self, run_id: str) -> list[GraphNode]:
        """Return graph nodes for one run."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM graph_nodes WHERE run_id=? ORDER BY created_at", (run_id,)
            ).fetchall()
        return [self._row_to_node(row) for row in rows]

    def list_runs(self) -> list[str]:
        """List run IDs present in the graph."""
        with self._connect() as conn:
            rows = conn.execute("SELECT DISTINCT run_id FROM graph_nodes ORDER BY run_id").fetchall()
        return [row[0] for row in rows]

    def stats(self) -> dict[str, int]:
        """Return {'total_nodes': N, 'total_runs': N, 'reuse_count': N}."""
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM graph_nodes").fetchone()[0]
            runs = conn.execute("SELECT COUNT(DISTINCT run_id) FROM graph_nodes").fetchone()[0]
            reused = conn.execute(
                "SELECT COUNT(*) FROM graph_nodes WHERE reuse_source_id IS NOT NULL"
            ).fetchone()[0]
        return {"total_nodes": int(total), "total_runs": int(runs), "reuse_count": int(reused)}

    def export_dot(self) -> str:
        """Return a Graphviz DOT string of the full DAG."""
        with self._connect() as conn:
            rows = conn.execute("SELECT node_id, step_id, parent_node_ids FROM graph_nodes").fetchall()
        lines = ["digraph helix {"]
        for node_id, step_id, parents_json in rows:
            lines.append(f'  "{node_id}" [label="{step_id}"];')
            for parent in json.loads(parents_json):
                lines.append(f'  "{parent}" -> "{node_id}";')
        lines.append("}")
        return "\n".join(lines)
