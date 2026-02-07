"""Tests for the brocode_query_codebase tool.

Covers: unfiltered query, type filter, path glob filter, invalid type,
claim status in results, and limit enforcement.
"""

from __future__ import annotations

import pytest

from brocode_mcp.server import brocode_query_codebase as _tool

# Access the underlying async function, bypassing FastMCP's FunctionTool wrapper.
query_codebase = _tool.fn


@pytest.mark.asyncio
async def test_query_all_nodes(mock_db, mock_ctx):
    """Query with no filters should return matching nodes."""
    mock_db.query_codebase.return_value = [
        {
            "node_labels": ["File"],
            "node_path": "src/app.py",
            "node_name": "app.py",
            "claimed_by": None,
            "claim_reason": None,
        },
        {
            "node_labels": ["Directory"],
            "node_path": "src",
            "node_name": "src",
            "claimed_by": None,
            "claim_reason": None,
        },
    ]

    result = await query_codebase(codebase_name="my-repo", ctx=mock_ctx)

    assert result["status"] == "ok"
    assert result["count"] == 2
    assert result["codebase"] == "my-repo"


@pytest.mark.asyncio
async def test_query_filter_by_type(mock_db, mock_ctx):
    """Filtering by node_type should pass through to the client."""
    mock_db.query_codebase.return_value = [
        {
            "node_labels": ["File"],
            "node_path": "src/app.py",
            "node_name": "app.py",
            "claimed_by": None,
            "claim_reason": None,
        },
    ]

    result = await query_codebase(
        codebase_name="my-repo", node_type="File", ctx=mock_ctx
    )

    assert result["status"] == "ok"
    mock_db.query_codebase.assert_awaited_once_with(
        codebase="my-repo", path_filter=None, node_type="File", limit=50
    )


@pytest.mark.asyncio
async def test_query_filter_by_path_glob(mock_db, mock_ctx):
    """Path glob filter should be passed to the client."""
    mock_db.query_codebase.return_value = []

    result = await query_codebase(
        codebase_name="my-repo", path_filter="src/*.py", ctx=mock_ctx
    )

    assert result["status"] == "ok"
    mock_db.query_codebase.assert_awaited_once_with(
        codebase="my-repo", path_filter="src/*.py", node_type=None, limit=50
    )


@pytest.mark.asyncio
async def test_query_invalid_type(mock_db, mock_ctx):
    """Invalid node_type should return an error without querying."""
    result = await query_codebase(
        codebase_name="my-repo", node_type="InvalidType", ctx=mock_ctx
    )

    assert result["status"] == "error"
    assert "invalid" in result["message"].lower()
    mock_db.query_codebase.assert_not_awaited()


@pytest.mark.asyncio
async def test_query_shows_claim_status(mock_db, mock_ctx):
    """Nodes with active claims should show claimed_by in results."""
    mock_db.query_codebase.return_value = [
        {
            "node_labels": ["File"],
            "node_path": "src/app.py",
            "node_name": "app.py",
            "claimed_by": "claude-1",
            "claim_reason": "editing",
        },
        {
            "node_labels": ["File"],
            "node_path": "src/utils.py",
            "node_name": "utils.py",
            "claimed_by": None,
            "claim_reason": None,
        },
    ]

    result = await query_codebase(codebase_name="my-repo", ctx=mock_ctx)

    claimed = result["nodes"][0]
    unclaimed = result["nodes"][1]
    assert claimed["claimed_by"] == "claude-1"
    assert claimed["claim_reason"] == "editing"
    assert unclaimed["claimed_by"] is None


@pytest.mark.asyncio
async def test_query_respects_limit(mock_db, mock_ctx):
    """Custom limit should be passed through to the client."""
    mock_db.query_codebase.return_value = []

    await query_codebase(
        codebase_name="my-repo", limit=5, ctx=mock_ctx
    )

    mock_db.query_codebase.assert_awaited_once_with(
        codebase="my-repo", path_filter=None, node_type=None, limit=5
    )
