"""Tests for the brocode_release_node tool.

Covers: successful release with reindex, releasing nonexistent claim,
reindex when root_path missing from graph, reindex subprocess failure,
and file vs directory subtree clearing.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from brocode_mcp.server import brocode_release_node as _tool

# Access the underlying async function, bypassing FastMCP's FunctionTool wrapper.
release_node = _tool.fn


@pytest.mark.asyncio
async def test_release_and_reindex_file(mock_db, mock_ctx):
    """Releasing a file should clear it and reindex from the repo root."""
    mock_db.release_claim.return_value = {
        "agent_name": "claude-1",
        "labels": ["File"],
        "path": "src/app.py",
        "root_path": "/home/user/my-repo",
    }

    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"Done -- graph written.", b"")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await release_node(
            agent_name="claude-1",
            node_path="src/app.py",
            codebase_name="my-repo",
            ctx=mock_ctx,
        )

    assert result["status"] == "released"
    assert result["reindex_status"] == "success"
    # File node should be cleared (is_directory=False)
    mock_db.clear_subtree.assert_awaited_once_with("src/app.py", "my-repo", False)


@pytest.mark.asyncio
async def test_release_and_reindex_directory(mock_db, mock_ctx):
    """Releasing a directory should clear the subtree and reindex."""
    mock_db.release_claim.return_value = {
        "agent_name": "claude-1",
        "labels": ["Directory"],
        "path": "src/utils",
        "root_path": "/home/user/my-repo",
    }

    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"Done.", b"")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
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
async def test_release_reindex_cli_missing(mock_db, mock_ctx):
    """Missing repo-graph CLI should report error gracefully."""
    mock_db.release_claim.return_value = {
        "agent_name": "claude-1",
        "labels": ["File"],
        "path": "src/app.py",
        "root_path": "/home/user/my-repo",
    }

    with patch(
        "asyncio.create_subprocess_exec",
        side_effect=FileNotFoundError("python not found"),
    ):
        result = await release_node(
            agent_name="claude-1",
            node_path="src/app.py",
            codebase_name="my-repo",
            ctx=mock_ctx,
        )

    assert result["status"] == "released"
    assert result["reindex_status"] == "error"
    assert "not found" in result["reindex_message"].lower()
    # Subtree should still be cleared even if reindex fails
    mock_db.clear_subtree.assert_awaited_once()


@pytest.mark.asyncio
async def test_release_reindex_subprocess_failure(mock_db, mock_ctx):
    """Non-zero exit from repo-graph should report error."""
    mock_db.release_claim.return_value = {
        "agent_name": "claude-1",
        "labels": ["File"],
        "path": "src/app.py",
        "root_path": "/home/user/my-repo",
    }

    mock_proc = AsyncMock()
    mock_proc.returncode = 1
    mock_proc.communicate.return_value = (b"", b"Error: invalid path")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await release_node(
            agent_name="claude-1",
            node_path="src/app.py",
            codebase_name="my-repo",
            ctx=mock_ctx,
        )

    assert result["status"] == "released"
    assert result["reindex_status"] == "error"
    assert "invalid path" in result["reindex_message"].lower()
