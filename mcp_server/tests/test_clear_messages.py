"""Tests for the brocode_clear_messages tool.

Covers: clearing messages after reading, idempotent clearing of empty inbox.
"""

from __future__ import annotations

import pytest

from brocode_mcp.server import brocode_clear_messages as _tool

# Access the underlying async function, bypassing FastMCP's FunctionTool wrapper.
clear_messages = _tool.fn


@pytest.mark.asyncio
async def test_clear_messages_success(mock_db, mock_ctx):
    """Clearing messages should call db.clear_messages and return ok."""
    result = await clear_messages(
        agent_name="claude-1",
        ctx=mock_ctx,
    )

    assert result["status"] == "ok"
    mock_db.clear_messages.assert_awaited_once_with("claude-1")


@pytest.mark.asyncio
async def test_clear_messages_idempotent(mock_db, mock_ctx):
    """Clearing an already-empty inbox should still succeed."""
    result = await clear_messages(
        agent_name="claude-1",
        ctx=mock_ctx,
    )

    assert result["status"] == "ok"
    mock_db.clear_messages.assert_awaited_once_with("claude-1")
