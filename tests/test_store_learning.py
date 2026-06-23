"""Tests for the store_learning tool's structured output handling.

The MCP wrapper shells out to OPC's store_learning.py with --json and must
surface store-vs-skip-vs-supersede distinctly, so a caller can tell whether a
--supersedes actually took effect rather than silently falling back to a dedup
block (OPC PR #236 / issue #235).
"""

import json
from types import SimpleNamespace
from unittest.mock import patch

import main


def _proc(returncode=0, stdout="", stderr=""):
    """Build a stand-in for subprocess.CompletedProcess."""
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


# ---------------------------------------------------------------------------
# _parse_store_output (pure function)
# ---------------------------------------------------------------------------


def test_parse_stored_success():
    payload = {
        "success": True,
        "memory_id": "new-uuid-123",
        "backend": "postgres",
        "content_length": 42,
    }
    result = main._parse_store_output(0, json.dumps(payload), "")

    assert result["success"] is True
    assert result["stored"] is True
    assert result["skipped"] is False
    assert result["memory_id"] == "new-uuid-123"
    assert "superseded" not in result


def test_parse_supersede_surfaces_superseded_id():
    payload = {
        "success": True,
        "memory_id": "new-uuid-123",
        "superseded": "11111111-1111-1111-1111-111111111111",
    }
    result = main._parse_store_output(0, json.dumps(payload), "")

    assert result["stored"] is True
    assert result["superseded"] == "11111111-1111-1111-1111-111111111111"
    assert "superseded" in result["message"]


def test_parse_skip_is_not_reported_as_stored():
    """A dedup skip exits 0 with success=True; it must NOT look like a store."""
    payload = {
        "success": True,
        "skipped": True,
        "reason": "duplicate",
        "existing_id": "22222222-2222-2222-2222-222222222222",
    }
    result = main._parse_store_output(0, json.dumps(payload), "")

    assert result["success"] is True
    assert result["skipped"] is True
    assert result["stored"] is False
    assert result["reason"] == "duplicate"
    assert result["existing_id"] == "22222222-2222-2222-2222-222222222222"
    assert "skipped" in result["message"].lower()


def test_parse_genuine_failure_nonzero_exit():
    payload = {"success": False, "error": "No content provided"}
    result = main._parse_store_output(1, json.dumps(payload), "")

    assert result["success"] is False
    assert result["stored"] is False
    assert "No content provided" in result["error"]


def test_parse_non_json_stdout_falls_back():
    """Older script or a crash may emit non-JSON; preserve raw output."""
    result = main._parse_store_output(0, "Learning stored (id: abc)", "")

    assert result["success"] is True
    assert result["stored"] is False
    assert "Learning stored" in result["message"]


def test_parse_non_json_failure_uses_stderr():
    result = main._parse_store_output(1, "", "boom traceback")

    assert result["success"] is False
    assert "boom traceback" in result["message"]


# ---------------------------------------------------------------------------
# store_learning tool (passes --json, delegates to the parser)
# ---------------------------------------------------------------------------


def test_store_learning_passes_json_flag():
    payload = {"success": True, "memory_id": "abc", "backend": "postgres"}
    captured = {}

    def fake_run(script, args):
        captured["script"] = script
        captured["args"] = args
        return _proc(0, json.dumps(payload), "")

    with patch.object(main, "run_opc_script", fake_run), patch.object(
        main, "_detect_project", lambda: ""
    ):
        result = main.store_learning(content="hi", supersedes="")

    assert "--json" in captured["args"]
    assert result["stored"] is True
    assert result["memory_id"] == "abc"


def test_store_learning_forwards_supersedes_and_reports_link():
    payload = {
        "success": True,
        "memory_id": "new-id",
        "superseded": "33333333-3333-3333-3333-333333333333",
    }
    captured = {}

    def fake_run(script, args):
        captured["args"] = args
        return _proc(0, json.dumps(payload), "")

    with patch.object(main, "run_opc_script", fake_run), patch.object(
        main, "_detect_project", lambda: ""
    ):
        result = main.store_learning(
            content="corrected",
            supersedes="33333333-3333-3333-3333-333333333333",
        )

    assert "--supersedes" in captured["args"]
    idx = captured["args"].index("--supersedes")
    assert captured["args"][idx + 1] == "33333333-3333-3333-3333-333333333333"
    assert result["superseded"] == "33333333-3333-3333-3333-333333333333"


def test_store_learning_skip_not_success_message():
    payload = {
        "success": True,
        "skipped": True,
        "reason": "duplicate",
        "existing_id": "22222222-2222-2222-2222-222222222222",
    }

    with patch.object(
        main, "run_opc_script", lambda s, a: _proc(0, json.dumps(payload), "")
    ), patch.object(main, "_detect_project", lambda: ""):
        result = main.store_learning(content="dup")

    assert result["skipped"] is True
    assert result["stored"] is False
