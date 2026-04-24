CREATE TABLE IF NOT EXISTS cache_entries (
    key TEXT PRIMARY KEY,
    step_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    response TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    latency_ms REAL NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    hit_count INTEGER NOT NULL DEFAULT 0,
    block_hashes TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cache_step ON cache_entries(step_id);
CREATE INDEX IF NOT EXISTS idx_cache_created ON cache_entries(created_at);

CREATE TABLE IF NOT EXISTS semantic_cache_entries (
    semantic_id TEXT PRIMARY KEY,
    cache_key TEXT NOT NULL,
    step_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    minimized_input TEXT NOT NULL,
    embedding TEXT NOT NULL,
    response TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    latency_ms REAL NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_semantic_step_model ON semantic_cache_entries(step_id, model_id);
