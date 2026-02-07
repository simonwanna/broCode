"""Tests for the brocode_get_messages tool.

Covers: retrieving parsed messages, empty inbox. Messages are read-only —
clearing is done via a separate brocode_clear_messages tool.
"""

from __future__ import annotations

import json

import pytest

from brocode_mcp.server import brocode_get_messages as _tool

# Access the underlying async function, bypassing FastMCP's FunctionTool wrapper.
get_messages = _tool.fn


@pytest.mark.asyncio
async def test_get_messages_returns_parsed_messages(mock_db, mock_ctx):
    """Messages stored as JSON strings should be parsed back to dicts."""
    mock_db.get_messages.return_value = [
        json.dumps({
            "from": "gemini-1",
            "content": "Can I access src/app.py?",
            "node_path": "src/app.py",
            "timestamp": "2026-02-07T12:30:00Z",
        }),
        json.dumps({
            "from": "claude-2",
            "content": "I'm done with utils.py, releasing now",
            "node_path": "src/utils.py",
            "timestamp": "2026-02-07T12:35:00Z",
        }),
    ]

    result = await get_messages(
        agent_name="claude-1",
        ctx=mock_ctx,
    )

    assert result["status"] == "ok"
    assert result["count"] == 2
    assert len(result["messages"]) == 2

    # Messages should be dicts, not raw JSON strings
    msg = result["messages"][0]
    assert isinstance(msg, dict)
    assert msg["from"] == "gemini-1"
    assert msg["content"] == "Can I access src/app.py?"
    assert msg["node_path"] == "src/app.py"


@pytest.mark.asyncio
async def test_get_messages_empty_inbox(mock_db, mock_ctx):
    """Agent with no messages should get an empty list."""
    mock_db.get_messages.return_value = []

    result = await get_messages(
        agent_name="claude-1",
        ctx=mock_ctx,
    )

    assert result["status"] == "ok"
    assert result["count"] == 0
    assert result["messages"] == []


@pytest.mark.asyncio
async def test_get_messages_does_not_clear(mock_db, mock_ctx):
    """get_messages should NOT clear messages — that's a separate tool."""
    mock_db.get_messages.return_value = [
        json.dumps({"from": "gemini-1", "content": "Hello", "node_path": "", "timestamp": "2026-02-07T12:30:00Z"}),
    ]

    await get_messages(
        agent_name="claude-1",
        ctx=mock_ctx,
    )

    mock_db.clear_messages.assert_not_awaited()
