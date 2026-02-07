"""Tests for the brocode_send_message tool.

Covers: successful send, empty message rejected, self-send rejected,
nonexistent target rejected, optional node_path handling.
"""

from __future__ import annotations

import json

import pytest

from brocode_mcp.server import brocode_send_message as _tool

# Access the underlying async function, bypassing FastMCP's FunctionTool wrapper.
send_message = _tool.fn


@pytest.mark.asyncio
async def test_send_message_success(mock_db, mock_ctx):
    """Sending a message to an existing agent should return 'sent' with count."""
    result = await send_message(
        from_agent="claude-1",
        to_agent="gemini-1",
        message="Can I access src/app.py? I need to update the return type.",
        ctx=mock_ctx,
    )

    assert result["status"] == "sent"
    assert result["to_agent"] == "gemini-1"
    assert "message_count" in result
    mock_db.check_agent_exists.assert_awaited_once_with("gemini-1")
    mock_db.send_message.assert_awaited_once()

    # Verify the JSON message stored contains expected fields
    call_args = mock_db.send_message.call_args
    stored_json = call_args[0][1]  # second positional arg
    stored = json.loads(stored_json)
    assert stored["from"] == "claude-1"
    assert stored["content"] == "Can I access src/app.py? I need to update the return type."
    assert "timestamp" in stored


@pytest.mark.asyncio
async def test_send_message_rejects_empty_message(mock_db, mock_ctx):
    """Empty message should be rejected."""
    result = await send_message(
        from_agent="claude-1",
        to_agent="gemini-1",
        message="",
        ctx=mock_ctx,
    )

    assert result["status"] == "error"
    assert "message" in result["message"].lower()
    mock_db.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_message_rejects_self_send(mock_db, mock_ctx):
    """Sending a message to yourself should be rejected."""
    result = await send_message(
        from_agent="claude-1",
        to_agent="claude-1",
        message="Hello me",
        ctx=mock_ctx,
    )

    assert result["status"] == "error"
    assert "yourself" in result["message"].lower() or "same" in result["message"].lower()
    mock_db.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_message_rejects_nonexistent_target(mock_db, mock_ctx):
    """Sending to a nonexistent agent should return error."""
    mock_db.check_agent_exists.return_value = None

    result = await send_message(
        from_agent="claude-1",
        to_agent="unknown-agent",
        message="Hello?",
        ctx=mock_ctx,
    )

    assert result["status"] == "error"
    assert "not found" in result["message"].lower()
    mock_db.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_message_includes_node_path(mock_db, mock_ctx):
    """When node_path is provided, it should be included in the stored message."""
    await send_message(
        from_agent="claude-1",
        to_agent="gemini-1",
        message="I need to modify the error handling here",
        node_path="src/app.py",
        ctx=mock_ctx,
    )

    call_args = mock_db.send_message.call_args
    stored_json = call_args[0][1]
    stored = json.loads(stored_json)
    assert stored["node_path"] == "src/app.py"


@pytest.mark.asyncio
async def test_send_message_without_node_path(mock_db, mock_ctx):
    """When node_path is not provided, message should still work with empty node_path."""
    await send_message(
        from_agent="claude-1",
        to_agent="gemini-1",
        message="General question about the codebase",
        ctx=mock_ctx,
    )

    call_args = mock_db.send_message.call_args
    stored_json = call_args[0][1]
    stored = json.loads(stored_json)
    assert stored["node_path"] == ""
