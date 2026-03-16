# OPC Memory Multi-System Migration History

Changes are spread across two repos (`opc-memory-mcp` and `opc`) plus config and database, so this file tracks everything in one place.

## Phase 1: Schema + Identity (No breaking changes)

Started: 2026-03-16

### 1. Database Schema Changes

**PostgreSQL (continuous_claude database):**
```sql
ALTER TABLE archival_memory ADD COLUMN host_id TEXT DEFAULT NULL;
ALTER TABLE archival_memory ADD COLUMN content_hash TEXT DEFAULT NULL;
ALTER TABLE sessions ADD COLUMN host_id TEXT DEFAULT NULL;

CREATE UNIQUE INDEX idx_archival_content_hash ON archival_memory (content_hash);
CREATE INDEX idx_archival_host ON archival_memory (host_id);
CREATE INDEX idx_sessions_host ON sessions (host_id);
```

**Backfill (2031 archival_memory rows, 3341 sessions rows):**
- `host_id` set to `'stephens-macbook'` for all existing rows
- `content_hash` computed as `SHA-256(content)` for all existing rows
- No duplicate content hashes found — unique constraint applied cleanly
- `embedding_model` column already existed (default `'bge'`, 2022 rows already `'voyage-code-3'`)

### 2. Config: `~/.claude/opc.json`

Added `host_id` and `host_name` fields:
```json
{
  "opc_dir": "/Users/stephenfeather/opc",
  "host_id": "stephens-macbook",
  "host_name": "Stephen's MacBook Pro"
}
```

### 3. Code: `opc-memory-mcp/main.py`

- Replaced `get_opc_dir()` with `load_opc_config()` — now loads `host_id` and `host_name` from `opc.json` alongside `opc_dir`
- Exports `OPC_DIR`, `HOST_ID`, `HOST_NAME` as module-level constants
- `store_learning` tool now passes `--host-id` to the underlying script when `HOST_ID` is configured

### 4. Code: `opc/scripts/core/store_learning.py`

- Added `import hashlib`
- `store_learning_v2()`: new `host_id` parameter
- Computes `content_hash` (SHA-256 of content) before storing
- Adds `embedding_model` to metadata (reads from `VOYAGE_EMBEDDING_MODEL` or `EMBEDDING_PROVIDER` env vars)
- Adds `host_id` to metadata
- Passes `content_hash` and `host_id` through to `memory.store()`
- New CLI argument: `--host-id`
- Return dict now includes `host_id`

### 5. Code: `opc/scripts/core/db/memory_service_pg.py`

- `store()` method: new parameters `content_hash` and `host_id`
- INSERT statements now include `content_hash` and `host_id` columns
- Added `ON CONFLICT (content_hash) DO NOTHING` — silently prevents exact-duplicate content from being inserted

### Verification

- Stored a test learning with `--host-id stephens-macbook` — all new fields populated correctly:
  - `host_id`: `stephens-macbook` (column)
  - `content_hash`: SHA-256 hex (column)
  - `embedding_model`: `voyage-code-3` (in metadata)
  - `host_id`: `stephens-macbook` (in metadata)
- Attempted duplicate store — `ON CONFLICT DO NOTHING` prevented second insert (only 1 row)
- Recall queries work unchanged — no breaking changes
- Cleaned up test data

**MCP server test:**
- `mcp__opc-memory__store_learning` — stored successfully, `content_hash` and `embedding_model` populated correctly
- `mcp__opc-memory__recall_learnings` — recall works unchanged
- `host_id` was empty string because MCP server was running with old `opc.json` (before `host_id` was added). Config is loaded at server startup — requires MCP server restart to pick up new `opc.json` values. After restart, `HOST_ID` will be `"stephens-macbook"` and passed to all store calls.
- Duplicate content_hash dedup confirmed working via `ON CONFLICT DO NOTHING`

