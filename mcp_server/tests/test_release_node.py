"""Tests for the brocode_release_node tool.

Covers: successful release with subtree reindex, releasing nonexistent claim,
reindex when root_path missing from graph, reindex function failure,
and file vs directory subtree clearing.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from brocode_mcp.server import brocode_release_node as _tool

# Access the underlying async function, bypassing FastMCP's FunctionTool wrapper.
release_node = _tool.fn


@pytest.mark.asyncio
async def test_release_and_reindex_file(mock_db, mock_ctx):
    """Releasing a file should clear it and reindex the file's parent subtree."""
    mock_db.release_claim.return_value = {
        "agent_name": "claude-1",
        "labels": ["File"],
        "path": "src/app.py",
        "root_path": "/home/user/my-repo",
    }

    with patch(
        "brocode_mcp.server._reindex_sync",
        return_value="Reindexed 'src/app.py': 0 dirs, 5 files, 10 functions, 3 classes",
    ) as mock_reindex:
        result = await release_node(
            agent_name="claude-1",
            node_path="src/app.py",
            codebase_name="my-repo",
            ctx=mock_ctx,
        )

    assert result["status"] == "released"
    assert result["reindex_status"] == "success"
    assert "5 files" in result["reindex_message"]
    # File node should be cleared (is_directory=False)
    mock_db.clear_subtree.assert_awaited_once_with("src/app.py", "my-repo", False)
    # Reindex scoped to subtree with correct args
    mock_reindex.assert_called_once_with(
        "/home/user/my-repo", "src/app.py", "my-repo", False
    )


@pytest.mark.asyncio
async def test_release_and_reindex_directory(mock_db, mock_ctx):
    """Releasing a directory should clear the subtree and reindex that directory."""
    mock_db.release_claim.return_value = {
        "agent_name": "claude-1",
        "labels": ["Directory"],
        "path": "src/utils",
        "root_path": "/home/user/my-repo",
    }

    with patch(
        "brocode_mcp.server._reindex_sync",
        return_value="Reindexed 'src/utils': 1 dirs, 3 files, 0 functions, 0 classes",
    ) as mock_reindex:
        result = await release_node(
            agent_name="claude-1",
            node_path="src/utils",
            codebase_name="my-repo",
            ctx=mock_ctx,
        )

    assert result["status"] == "released"
    assert result["reindex_status"] == "success"
    # Directory node should be cleared (is_directory=True)
    mock_db.clear_subtree.assert_awaited_once_with("src/utils", "my-repo", True)
    mock_reindex.assert_called_once_with(
        "/home/user/my-repo", "src/utils", "my-repo", True
    )


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
    mock_db.clear_subtree.assert_not_awaited()


@pytest.mark.asyncio
async def test_release_skips_reindex_when_no_root_path(mock_db, mock_ctx):
    """When the Codebase has no root_path, reindex should be skipped."""
    mock_db.release_claim.return_value = {
        "agent_name": "claude-1",
        "labels": ["File"],
        "path": "src/app.py",
        "root_path": "",
    }

    result = await release_node(
        agent_name="claude-1",
        node_path="src/app.py",
        codebase_name="my-repo",
        ctx=mock_ctx,
    )

    assert result["status"] == "released"
    assert result["reindex_status"] == "skipped"
    mock_db.clear_subtree.assert_not_awaited()


@pytest.mark.asyncio
async def test_release_reindex_failure(mock_db, mock_ctx):
    """Reindex errors should be reported gracefully without breaking release."""
    mock_db.release_claim.return_value = {
        "agent_name": "claude-1",
        "labels": ["File"],
        "path": "src/app.py",
        "root_path": "/home/user/my-repo",
    }

    with patch(
        "brocode_mcp.server._reindex_sync",
        side_effect=FileNotFoundError("Repo root '/home/user/my-repo' is not a directory"),
    ):
        result = await release_node(
            agent_name="claude-1",
            node_path="src/app.py",
            codebase_name="my-repo",
            ctx=mock_ctx,
        )

    assert result["status"] == "released"
    assert result["reindex_status"] == "error"
    assert "not a directory" in result["reindex_message"].lower()
    # Subtree should still be cleared even if reindex fails
    mock_db.clear_subtree.assert_awaited_once()
