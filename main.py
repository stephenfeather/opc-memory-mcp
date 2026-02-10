#!/usr/bin/env python3
"""OPC Memory MCP Server.

Exposes OPC memory scripts as MCP tools, handling working directory
and PYTHONPATH requirements automatically.
"""

import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field


def get_opc_dir() -> str:
    """Resolve OPC directory from env var or config file.

    Resolution order:
    1. CLAUDE_OPC_DIR environment variable (explicit override)
    2. ~/.claude/opc.json config file (persistent setting)
    3. Fallback to hardcoded default
    """
    # 1. Try env var
    env_dir = os.environ.get("CLAUDE_OPC_DIR")
    if env_dir and Path(env_dir).exists():
        return env_dir

    # 2. Try config file
    config_path = Path.home() / ".claude" / "opc.json"
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text())
            opc_dir = config.get("opc_dir")
            if opc_dir and Path(opc_dir).exists():
                return opc_dir
        except (json.JSONDecodeError, OSError):
            pass

    # 3. Fallback
    return "/Users/stephenfeather/opc"


# OPC directory where scripts live
OPC_DIR = get_opc_dir()


def run_opc_script(script: str, args: list[str]) -> subprocess.CompletedProcess:
    """Run an OPC script with correct working directory and PYTHONPATH."""
    cmd = ["uv", "run", "python", f"scripts/core/{script}"] + args
    return subprocess.run(
        cmd,
        cwd=OPC_DIR,
        env={**os.environ, "PYTHONPATH": "."},
        capture_output=True,
        text=True,
        timeout=60,
    )


# Create the MCP server
mcp = FastMCP("opc-memory")


@mcp.tool()
def store_learning(
    content: str = Field(description="The learning content to store"),
    learning_type: str = Field(
        description="Type: WORKING_SOLUTION, ARCHITECTURAL_DECISION, CODEBASE_PATTERN, FAILED_APPROACH, ERROR_FIX, USER_PREFERENCE, OPEN_THREAD",
        default="WORKING_SOLUTION",
    ),
    session_id: str = Field(description="Session identifier", default="mcp-session"),
    context: str = Field(description="What this relates to", default=""),
    tags: str = Field(description="Comma-separated tags", default=""),
    confidence: str = Field(description="high, medium, or low", default="medium"),
) -> dict[str, Any]:
    """Store a learning in the OPC memory system with embeddings for semantic recall."""
    args = [
        "--session-id", session_id,
        "--type", learning_type,
        "--content", content,
        "--confidence", confidence,
    ]

    if context:
        args.extend(["--context", context])
    if tags:
        args.extend(["--tags", tags])

    result = run_opc_script("store_learning.py", args)

    if result.returncode != 0:
        return {
            "success": False,
            "error": result.stderr or "Unknown error",
            "stdout": result.stdout,
        }

    return {
        "success": True,
        "message": result.stdout.strip() or "Learning stored successfully",
    }


@mcp.tool()
def recall_learnings(
    query: str = Field(description="Search query for semantic recall"),
    k: int = Field(description="Number of results to return", default=5),
    text_only: bool = Field(description="Fast text search without embeddings", default=False),
    vector_only: bool = Field(description="Pure vector/embedding search", default=False),
    threshold: float = Field(description="Similarity threshold (0.0-1.0)", default=0.2),
) -> dict[str, Any]:
    """Search the OPC memory system for relevant learnings using semantic search."""
    args = [
        "--query", query,
        "--k", str(k),
        "--threshold", str(threshold),
    ]

    if text_only:
        args.append("--text-only")
    if vector_only:
        args.append("--vector-only")

    result = run_opc_script("recall_learnings.py", args)

    if result.returncode != 0:
        return {
            "success": False,
            "error": result.stderr or "Unknown error",
            "stdout": result.stdout,
        }

    # Try to parse JSON output
    try:
        learnings = json.loads(result.stdout)
        return {
            "success": True,
            "learnings": learnings,
            "count": len(learnings) if isinstance(learnings, list) else 1,
        }
    except json.JSONDecodeError:
        # Return raw output if not JSON
        return {
            "success": True,
            "raw_output": result.stdout.strip(),
        }


@mcp.tool()
def index_artifacts(
    mode: str = Field(
        description="Indexing mode: all, handoffs, plans, continuity, or file",
        default="all",
    ),
    file_path: str = Field(
        description="Path to single file (required when mode=file)",
        default="",
    ),
) -> dict[str, Any]:
    """Index handoffs, plans, and continuity ledgers into the artifact database."""
    # Map mode to CLI flags (script uses --handoffs, --plans, etc., not --mode)
    if mode == "file":
        if not file_path:
            return {
                "success": False,
                "error": "file_path is required when mode=file",
            }
        args = ["--file", file_path]
    elif mode in ("all", "handoffs", "plans", "continuity"):
        args = [f"--{mode}"]
    else:
        return {
            "success": False,
            "error": f"Invalid mode: {mode}. Use: all, handoffs, plans, continuity, or file",
        }

    result = run_opc_script("artifact_index.py", args)

    if result.returncode != 0:
        return {
            "success": False,
            "error": result.stderr or "Unknown error",
            "stdout": result.stdout,
        }

    return {
        "success": True,
        "message": result.stdout.strip() or "Artifacts indexed successfully",
    }


@mcp.tool()
def mark_handoff(
    outcome: str = Field(
        description="Outcome: SUCCEEDED, PARTIAL_PLUS, PARTIAL_MINUS, or FAILED"
    ),
    handoff_id: str = Field(
        description="Specific handoff ID (uses latest if empty)",
        default="",
    ),
    notes: str = Field(description="Notes about the outcome", default=""),
) -> dict[str, Any]:
    """Mark a handoff with its outcome for tracking success rates."""
    args = ["--outcome", outcome]

    if handoff_id:
        args.extend(["--id", handoff_id])
    if notes:
        args.extend(["--notes", notes])

    result = run_opc_script("artifact_mark.py", args)

    if result.returncode != 0:
        return {
            "success": False,
            "error": result.stderr or "Unknown error",
            "stdout": result.stdout,
        }

    return {
        "success": True,
        "message": result.stdout.strip() or "Handoff marked successfully",
    }


@mcp.tool()
def query_artifacts(
    query: str = Field(description="Search query for artifact precedent"),
    artifact_type: str = Field(
        description="Type: handoffs, plans, continuity, or all",
        default="all",
    ),
    outcome: str = Field(
        description="Filter by outcome: SUCCEEDED, PARTIAL_PLUS, PARTIAL_MINUS, FAILED",
        default="",
    ),
    limit: int = Field(description="Maximum results to return", default=5),
    with_content: bool = Field(description="Include full file content", default=False),
    by_span_id: str = Field(description="Get handoff by Braintrust root_span_id", default=""),
) -> dict[str, Any]:
    """Search the Context Graph for relevant precedent from past sessions."""
    args = []

    if by_span_id:
        args.extend(["--by-span-id", by_span_id])
    else:
        args.extend(query.split())
        args.extend(["--type", artifact_type])
        args.extend(["--limit", str(limit)])
        if outcome:
            args.extend(["--outcome", outcome])

    if with_content:
        args.append("--with-content")

    args.append("--json")

    result = run_opc_script("artifact_query.py", args)

    if result.returncode != 0:
        return {
            "success": False,
            "error": result.stderr or "Unknown error",
            "stdout": result.stdout,
        }

    # Try to parse JSON output
    try:
        artifacts = json.loads(result.stdout)
        return {
            "success": True,
            "artifacts": artifacts,
            "count": len(artifacts) if isinstance(artifacts, list) else 1,
        }
    except json.JSONDecodeError:
        return {
            "success": True,
            "raw_output": result.stdout.strip(),
        }


def run_mcp_server():
    """Entry point for the MCP server."""
    # Handle signals for graceful shutdown in multi-session environments
    def signal_handler(signum, frame):
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run with stdio transport
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run_mcp_server()
