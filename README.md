# OPC Memory MCP Server

MCP server that exposes OPC memory scripts as tools for Claude Code and Claude Desktop.

This project provides an MCP interface to the **OPC (Opinionated Persistent Context)** memory system from [Continuous Claude v3](https://github.com/parcadei/Continuous-Claude-v3). OPC enables semantic memory storage and retrieval, allowing Claude to learn from past sessions and maintain context across conversations.

## Tools

| Tool | Description |
|------|-------------|
| `store_learning` | Store session learnings with embeddings for semantic recall |
| `recall_learnings` | Semantic search over stored learnings |
| `query_artifacts` | Search Context Graph for precedent from past sessions |
| `index_artifacts` | Index handoffs, plans, and continuity ledgers |
| `mark_handoff` | Mark handoff outcomes for tracking |
| `start_daemon` | Start the memory extraction daemon |
| `stop_daemon` | Stop the memory extraction daemon |
| `daemon_status` | Check daemon status and view recent logs |

## Prerequisites

This MCP server requires:

1. **OPC infrastructure from Continuous Claude v3** - The memory scripts and PostgreSQL database schema from the parent project
2. **PostgreSQL database** - Running with the OPC schema (sessions, file_claims, archival_memory tables)
3. **Environment variables** - `DATABASE_URL` pointing to your PostgreSQL instance

See the [Continuous Claude v3 repository](https://github.com/parcadei/Continuous-Claude-v3) for setup instructions.

## OPC Directory Configuration

The OPC directory path can be configured in two ways (in priority order):

### 1. Environment Variable (Override)

```bash
export CLAUDE_OPC_DIR="/path/to/your/opc"
```

Use this for temporary overrides or CI/CD environments.

### 2. Config File (Persistent)

Create `~/.claude/opc.json`:

```json
{
  "opc_dir": "/path/to/your/opc"
}
```

This is the recommended approach for persistent user configuration.

### Resolution Order

Hooks and scripts resolve OPC_DIR in this order:

| Priority | Source | Use Case |
|----------|--------|----------|
| 1 | `CLAUDE_OPC_DIR` env var | Explicit override, CI/CD |
| 2 | `~/.claude/opc.json` | Persistent user preference |
| 3 | `${CLAUDE_PROJECT_DIR}/opc` | Project-local setup |
| 4 | `~/.claude` | Global installation |

### Hook Integration

If you're building hooks that need to reference OPC infrastructure, use the shared `opc-path.ts` module. See the `examples/hooks/` directory for a complete example you can copy to your `~/.claude/hooks/src/shared/` directory.

### MCP Server Resolution

The `main.py` MCP server uses the same resolution logic:

```python
def get_opc_dir() -> str:
    # 1. CLAUDE_OPC_DIR env var
    # 2. ~/.claude/opc.json config file
    # 3. Fallback default
```

This means the MCP server will automatically use your configured OPC path.

## Note on Skills

If you have Claude Code skills that reference OPC memory tools (e.g., `/recall`, `/remember`), you may need to update them to use the MCP tool names:

| Skill Reference | MCP Tool Name |
|-----------------|---------------|
| `store_learning` | `mcp__opc-memory__store_learning` |
| `recall_learnings` | `mcp__opc-memory__recall_learnings` |
| `query_artifacts` | `mcp__opc-memory__query_artifacts` |
| `index_artifacts` | `mcp__opc-memory__index_artifacts` |
| `mark_handoff` | `mcp__opc-memory__mark_handoff` |
| `start_daemon` | `mcp__opc-memory__start_daemon` |
| `stop_daemon` | `mcp__opc-memory__stop_daemon` |
| `daemon_status` | `mcp__opc-memory__daemon_status` |

## Installation

```bash
cd /Users/stephenfeather/Tools/opc-memory-mcp
uv sync
```

## Usage

### Run directly

```bash
uv run opc-memory-server
```

### Claude Desktop Configuration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "opc-memory": {
      "command": "uv",
      "args": ["--directory", "/Users/stephenfeather/Tools/opc-memory-mcp", "run", "opc-memory-server"]
    }
  }
}
```

### Claude Code Configuration

Add to `.claude/settings.json` or global settings:

```json
{
  "mcpServers": {
    "opc-memory": {
      "command": "uv",
      "args": ["--directory", "/Users/stephenfeather/Tools/opc-memory-mcp", "run", "opc-memory-server"]
    }
  }
}
```

## Tool Examples

### store_learning

```
Store a learning about hook development patterns.

Parameters:
- content: "TypeScript hooks require npm install before they work"
- learning_type: "WORKING_SOLUTION"
- context: "hook development"
- tags: "hooks,typescript"
- confidence: "high"
```

### recall_learnings

```
Search for past learnings about authentication.

Parameters:
- query: "authentication patterns"
- k: 5
- text_only: false (use embeddings)
```

### index_artifacts

```
Index all artifacts:
- mode: "all"

Index specific file:
- mode: "file"
- file_path: "/path/to/handoff.md"
```

### mark_handoff

```
Mark the latest handoff as successful:
- outcome: "SUCCEEDED"
- notes: "All tasks completed"
```

### Daemon Management

```
Check daemon status:
daemon_status()
# Returns: running status, PID, recent log entries

Start the daemon:
start_daemon()
# Starts memory extraction daemon if not running

Stop the daemon:
stop_daemon()
# Stops the running daemon
```

## Development

Test the server:

```bash
# Check it starts without errors
uv run opc-memory-server &
PID=$!
sleep 2
kill $PID

# Test individual tools via subprocess
uv run python -c "
from main import store_learning, recall_learnings
result = recall_learnings(query='test', k=1)
print(result)
"
```
