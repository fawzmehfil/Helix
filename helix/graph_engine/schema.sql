CREATE TABLE IF NOT EXISTS graph_nodes (
    node_id TEXT PRIMARY KEY,
    step_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    output_hash TEXT NOT NULL,
    response TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    latency_ms REAL NOT NULL,
    model_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    reuse_source_id TEXT,
    parent_node_ids TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_graph_input ON graph_nodes(input_hash, model_id);
CREATE INDEX IF NOT EXISTS idx_graph_run ON graph_nodes(run_id);
CREATE INDEX IF NOT EXISTS idx_graph_step ON graph_nodes(step_id);

