"""Tests for the brocode_get_active_agents tool.

Covers: no agents, single agent with multiple claims, multiple agents,
filtering by codebase, and no-filter returns all.
"""

from __future__ import annotations

import pytest

from brocode_mcp.server import brocode_get_active_agents as _tool

# Access the underlying async function, bypassing FastMCP's FunctionTool wrapper.
get_active_agents = _tool.fn


@pytest.mark.asyncio
async def test_no_active_agents(mock_db, mock_ctx):
    """When no claims exist, should return empty agents list."""
    result = await get_active_agents(ctx=mock_ctx)

    assert result["status"] == "ok"
    assert result["agent_count"] == 0
    assert result["agents"] == []


@pytest.mark.asyncio
async def test_single_agent_multiple_claims(mock_db, mock_ctx):
    """One agent with multiple claims should be grouped under one entry."""
    mock_db.get_active_agents.return_value = [
        {
            "agent_name": "claude-1",
            "agent_model": "claude",
            "node_labels": ["File"],
            "node_path": "src/app.py",
            "claim_reason": "editing",
        },
        {
            "agent_name": "claude-1",
            "agent_model": "claude",
            "node_labels": ["File"],
            "node_path": "src/utils.py",
            "claim_reason": "refactoring",
        },
        {
            "agent_name": "claude-1",
            "agent_model": "claude",
            "node_labels": ["Directory"],
            "node_path": "src/models",
            "claim_reason": "",
        },
    ]

    result = await get_active_agents(ctx=mock_ctx)

    assert result["agent_count"] == 1
    agent = result["agents"][0]
    assert agent["agent_name"] == "claude-1"
    assert len(agent["claims"]) == 3


@pytest.mark.asyncio
async def test_multiple_agents(mock_db, mock_ctx):
    """Multiple agents should each appear as separate entries."""
    mock_db.get_active_agents.return_value = [
        {
            "agent_name": "claude-1",
            "agent_model": "claude",
            "node_labels": ["File"],
            "node_path": "src/app.py",
            "claim_reason": "",
        },
        {
            "agent_name": "gemini-1",
            "agent_model": "gemini",
            "node_labels": ["Directory"],
            "node_path": "src/db",
            "claim_reason": "schema migration",
        },
    ]

    result = await get_active_agents(ctx=mock_ctx)

    assert result["agent_count"] == 2
    names = {a["agent_name"] for a in result["agents"]}
    assert names == {"claude-1", "gemini-1"}


@pytest.mark.asyncio
async def test_filter_by_codebase(mock_db, mock_ctx):
    """Passing codebase_name should filter to that codebase."""
    await get_active_agents(codebase_name="my-repo", ctx=mock_ctx)

    mock_db.get_active_agents.assert_awaited_once_with("my-repo")


@pytest.mark.asyncio
async def test_no_filter_returns_all(mock_db, mock_ctx):
    """Empty codebase_name should query all codebases."""
    await get_active_agents(codebase_name="", ctx=mock_ctx)

    mock_db.get_active_agents.assert_awaited_once_with(None)
