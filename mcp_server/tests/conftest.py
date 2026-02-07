"""Shared test fixtures for the broCode MCP server test suite.

Testing strategy: We mock the Neo4jClient so tests run without a live
Neo4j instance. Each test configures the mock's return values to simulate
different graph states (node exists, claim conflict, etc.).

Tools are tested by calling the underlying function (.fn attribute) of
each FunctionTool, bypassing FastMCP's decorator wrapper. The mock Context
injects the mock DB via request_context.lifespan_context (FastMCP >=2.3).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_db() -> AsyncMock:
    """Create a mock Neo4jClient with all async methods stubbed.

    Default behavior: node exists, no existing claims, claim succeeds.
    Override return values in individual tests to simulate different scenarios.
    """
    db = AsyncMock()
    db.check_node_exists.return_value = {
        "labels": ["File"],
        "path": "src/app.py",
        "name": "app.py",
    }
    db.check_existing_claim.return_value = []
    db.create_claim.return_value = {
        "labels": ["File"],
        "path": "src/app.py",
        "name": "app.py",
    }
    db.release_claim.return_value = {
        "agent_name": "claude-1",
        "labels": ["File"],
        "path": "src/app.py",
    }
    db.get_active_agents.return_value = []
    db.query_codebase.return_value = []
    # Messaging defaults
    db.check_agent_exists.return_value = {"name": "gemini-1", "model": "gemini"}
    db.send_message.return_value = {"message_count": 1}
    db.get_messages.return_value = []
    db.clear_messages.return_value = None
    # Agent cleanup defaults
    db.count_agent_claims.return_value = 0
    db.delete_agent.return_value = None
    # Graph update (upsert/delete) defaults — all return None (void)
    db.upsert_file.return_value = None
    db.upsert_directory.return_value = None
    db.upsert_function.return_value = None
    db.upsert_class.return_value = None
    db.delete_file.return_value = None
    db.delete_directory.return_value = None
    db.delete_function.return_value = None
    db.delete_class.return_value = None
    return db


@pytest.fixture
def mock_ctx(mock_db: AsyncMock) -> MagicMock:
    """Create a mock FastMCP Context with mock_db in the lifespan context.

    FastMCP >=2.3 stores the lifespan dict at
    ctx.request_context.lifespan_context (not ctx.lifespan_context).
    Tools access it via the _get_db() helper in server.py.
    """
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"db": mock_db}
    return ctx
