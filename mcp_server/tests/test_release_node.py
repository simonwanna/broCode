"""Tests for the brocode_release_node tool.

Covers: successful release with agent cleanup, releasing nonexistent claim,
agent preserved when other claims remain, and no reindex fields in response.
"""

from __future__ import annotations

import pytest

from brocode_mcp.server import brocode_release_node as _tool

# Access the underlying async function, bypassing FastMCP's FunctionTool wrapper.
release_node = _tool.fn


@pytest.mark.asyncio
async def test_release_success(mock_db, mock_ctx):
    """Releasing a claimed node should return 'released' and delete the agent."""
    mock_db.release_claim.return_value = {
        "agent_name": "claude-1",
        "labels": ["File"],
        "path": "src/app.py",
    }
    mock_db.count_agent_claims.return_value = 0

    result = await release_node(
        agent_name="claude-1",
        node_path="src/app.py",
        codebase_name="my-repo",
        ctx=mock_ctx,
    )

    assert result["status"] == "released"
    assert result["node_path"] == "src/app.py"
    assert result["agent_name"] == "claude-1"
    # Agent should be deleted since no claims remain
    mock_db.delete_agent.assert_awaited_once_with("claude-1")


@pytest.mark.asyncio
async def test_release_nonexistent_claim(mock_db, mock_ctx):
    """Releasing a claim that doesn't exist should return 'not_found'."""
    mock_db.release_claim.return_value = None

    result = await release_node(
        agent_name="claude-1",
        node_path="src/app.py",
        codebase_name="my-repo",
        ctx=mock_ctx,
    )

    assert result["status"] == "not_found"
    assert "no claim" in result["message"].lower()


@pytest.mark.asyncio
async def test_release_keeps_agent_when_claims_remain(mock_db, mock_ctx):
    """Agent node should NOT be deleted if it still has other claims."""
    mock_db.release_claim.return_value = {
        "agent_name": "claude-1",
        "labels": ["File"],
        "path": "src/app.py",
    }
    mock_db.count_agent_claims.return_value = 2

    result = await release_node(
        agent_name="claude-1",
        node_path="src/app.py",
        codebase_name="my-repo",
        ctx=mock_ctx,
    )

    assert result["status"] == "released"
    mock_db.delete_agent.assert_not_awaited()


@pytest.mark.asyncio
async def test_release_has_no_reindex_fields(mock_db, mock_ctx):
    """Response should not contain any reindex-related fields."""
    mock_db.release_claim.return_value = {
        "agent_name": "claude-1",
        "labels": ["File"],
        "path": "src/app.py",
    }
    mock_db.count_agent_claims.return_value = 0

    result = await release_node(
        agent_name="claude-1",
        node_path="src/app.py",
        codebase_name="my-repo",
        ctx=mock_ctx,
    )

    assert "reindex_status" not in result
    assert "reindex_message" not in result
