"""Tests for the brocode_claim_node tool.

Covers: successful claim, nonexistent node, idempotent re-claim by same
agent, conflict when another agent holds the claim, directory claims,
and claim_reason validation (must be a non-empty free-text description).
"""

from __future__ import annotations

import pytest

from brocode_mcp.server import brocode_claim_node as _tool

# Access the underlying async function, bypassing FastMCP's FunctionTool wrapper.
claim_node = _tool.fn


@pytest.mark.asyncio
async def test_claim_existing_node_success(mock_db, mock_ctx):
    """Claiming an unclaimed, existing node should return status 'claimed'."""
    result = await claim_node(
        agent_name="claude-1",
        agent_model="claude",
        node_path="src/app.py",
        codebase_name="my-repo",
        claim_reason="Refactoring error handling",
        ctx=mock_ctx,
    )

    assert result["status"] == "claimed"
    assert result["node_path"] == "src/app.py"
    assert result["agent_name"] == "claude-1"
    mock_db.check_node_exists.assert_awaited_once_with("src/app.py", "my-repo")
    mock_db.create_claim.assert_awaited_once()


@pytest.mark.asyncio
async def test_claim_nonexistent_node(mock_db, mock_ctx):
    """Claiming a node that doesn't exist in the graph should return error."""
    mock_db.check_node_exists.return_value = None

    result = await claim_node(
        agent_name="claude-1",
        agent_model="claude",
        node_path="nonexistent/file.py",
        codebase_name="my-repo",
        claim_reason="Adding new feature",
        ctx=mock_ctx,
    )

    assert result["status"] == "error"
    assert "not found" in result["message"].lower()
    mock_db.create_claim.assert_not_awaited()


@pytest.mark.asyncio
async def test_claim_already_yours_is_idempotent(mock_db, mock_ctx):
    """Re-claiming a node you already own should return 'already_yours'."""
    mock_db.check_existing_claim.return_value = [
        {"agent_name": "claude-1", "agent_model": "claude", "claim_reason": "Updating input validation"}
    ]

    result = await claim_node(
        agent_name="claude-1",
        agent_model="claude",
        node_path="src/app.py",
        codebase_name="my-repo",
        claim_reason="Updating input validation",
        ctx=mock_ctx,
    )

    assert result["status"] == "already_yours"
    mock_db.create_claim.assert_not_awaited()


@pytest.mark.asyncio
async def test_claim_conflict_another_agent(mock_db, mock_ctx):
    """Claiming a node held by another agent should return 'conflict'."""
    mock_db.check_existing_claim.return_value = [
        {"agent_name": "gemini-1", "agent_model": "gemini", "claim_reason": "Fixing authentication bug"}
    ]

    result = await claim_node(
        agent_name="claude-1",
        agent_model="claude",
        node_path="src/app.py",
        codebase_name="my-repo",
        claim_reason="Refactoring module imports",
        ctx=mock_ctx,
    )

    assert result["status"] == "conflict"
    assert "gemini-1" in result["message"]
    assert result["claimed_by"] == "gemini-1"
    mock_db.create_claim.assert_not_awaited()


@pytest.mark.asyncio
async def test_claim_accepts_descriptive_reason(mock_db, mock_ctx):
    """Free-text descriptive claim reason should be passed through to create_claim."""
    await claim_node(
        agent_name="claude-1",
        agent_model="claude",
        node_path="src/app.py",
        codebase_name="my-repo",
        claim_reason="Changes to input parameters and return statement",
        ctx=mock_ctx,
    )

    mock_db.create_claim.assert_awaited_once_with(
        "claude-1", "claude", "src/app.py", "my-repo",
        "Changes to input parameters and return statement"
    )


@pytest.mark.asyncio
async def test_claim_rejects_empty_reason(mock_db, mock_ctx):
    """Empty claim_reason should be rejected — agents must describe their intent."""
    result = await claim_node(
        agent_name="claude-1",
        agent_model="claude",
        node_path="src/app.py",
        codebase_name="my-repo",
        claim_reason="",
        ctx=mock_ctx,
    )

    assert result["status"] == "error"
    assert "claim_reason is required" in result["message"]
    mock_db.check_node_exists.assert_not_awaited()
    mock_db.create_claim.assert_not_awaited()


@pytest.mark.asyncio
async def test_claim_rejects_whitespace_only_reason(mock_db, mock_ctx):
    """Whitespace-only claim_reason should be rejected."""
    result = await claim_node(
        agent_name="claude-1",
        agent_model="claude",
        node_path="src/app.py",
        codebase_name="my-repo",
        claim_reason="   \t\n  ",
        ctx=mock_ctx,
    )

    assert result["status"] == "error"
    assert "claim_reason is required" in result["message"]
    mock_db.check_node_exists.assert_not_awaited()
    mock_db.create_claim.assert_not_awaited()


@pytest.mark.asyncio
async def test_claim_directory_node(mock_db, mock_ctx):
    """Claiming a Directory node should work the same as claiming a File."""
    mock_db.check_node_exists.return_value = {
        "labels": ["Directory"],
        "path": "src/utils",
        "name": "utils",
    }
    mock_db.create_claim.return_value = {
        "labels": ["Directory"],
        "path": "src/utils",
        "name": "utils",
    }

    result = await claim_node(
        agent_name="claude-1",
        agent_model="claude",
        node_path="src/utils",
        codebase_name="my-repo",
        claim_reason="Adding new utility functions",
        ctx=mock_ctx,
    )

    assert result["status"] == "claimed"
    assert result["node_path"] == "src/utils"
