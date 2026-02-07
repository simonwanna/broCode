"""Tests for broCode MCP resource endpoints.

Verifies that all four static resources are registered on the FastMCP
server instance and return non-empty markdown content.

Resources are static (no DB calls), so no mocking is needed — we only
need the `mcp` server instance.

The @mcp.resource() decorator wraps functions into FunctionResource
objects (like @mcp.tool wraps into FunctionTool). Access the raw
function via the `.fn` attribute.
"""

from __future__ import annotations

import pytest

from brocode_mcp.server import (
    agent_workflow,
    graph_schema,
    messaging_protocol,
    mcp,
    update_graph_examples,
)

# All resource URIs that should be registered.
EXPECTED_URIS = [
    "brocode://agent-workflow",
    "brocode://graph-schema",
    "brocode://update-graph-examples",
    "brocode://messaging",
]


# ------------------------------------------------------------------
# Registration tests
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_resource_uris_registered():
    """All four brocode:// resources should appear in mcp.get_resources()."""
    resources = await mcp.get_resources()
    registered_uris = set(resources.keys())
    for uri in EXPECTED_URIS:
        assert uri in registered_uris, f"Resource '{uri}' not registered"


@pytest.mark.asyncio
async def test_resource_count():
    """Exactly 4 resources should be registered."""
    resources = await mcp.get_resources()
    assert len(resources) == len(EXPECTED_URIS)


# ------------------------------------------------------------------
# Content tests — call the raw functions via .fn
# ------------------------------------------------------------------


def test_agent_workflow_returns_nonempty_string():
    """agent_workflow should return a non-empty markdown string."""
    content = agent_workflow.fn()
    assert isinstance(content, str)
    assert len(content) > 0
    assert "brocode_claim_node" in content


def test_graph_schema_returns_nonempty_string():
    """graph_schema should return a non-empty markdown string."""
    content = graph_schema.fn()
    assert isinstance(content, str)
    assert len(content) > 0
    assert "Codebase" in content
    assert "CONTAINS_FILE" in content


def test_update_graph_examples_returns_nonempty_string():
    """update_graph_examples should return a non-empty markdown string."""
    content = update_graph_examples.fn()
    assert isinstance(content, str)
    assert len(content) > 0
    assert '"upsert"' in content
    assert '"delete"' in content


def test_messaging_protocol_returns_nonempty_string():
    """messaging_protocol should return a non-empty markdown string."""
    content = messaging_protocol.fn()
    assert isinstance(content, str)
    assert len(content) > 0
    assert "brocode_send_message" in content
    assert "brocode_get_messages" in content


# ------------------------------------------------------------------
# Content quality tests — check key sections are present
# ------------------------------------------------------------------


def test_agent_workflow_covers_full_lifecycle():
    """Workflow resource should mention all lifecycle steps."""
    content = agent_workflow.fn()
    expected_tools = [
        "brocode_get_active_agents",
        "brocode_query_codebase",
        "brocode_claim_node",
        "brocode_update_graph",
        "brocode_release_node",
    ]
    for tool in expected_tools:
        assert tool in content, f"Workflow missing mention of {tool}"


def test_graph_schema_lists_all_node_types():
    """Schema resource should document all node types."""
    content = graph_schema.fn()
    for node_type in ["Codebase", "Directory", "File", "Function", "Class", "Agent"]:
        assert node_type in content, f"Schema missing node type {node_type}"


def test_graph_schema_lists_all_relationships():
    """Schema resource should document all relationship types."""
    content = graph_schema.fn()
    for rel in [
        "CONTAINS_DIR",
        "CONTAINS_FILE",
        "DEFINES_FUNCTION",
        "DEFINES_CLASS",
        "HAS_METHOD",
        "CLAIM",
    ]:
        assert rel in content, f"Schema missing relationship {rel}"


def test_update_graph_examples_covers_all_node_types():
    """Examples resource should show upsert/delete for all node types."""
    content = update_graph_examples.fn()
    for node_type in ["File", "Directory", "Function", "Class"]:
        assert node_type in content, f"Examples missing node type {node_type}"


def test_messaging_protocol_covers_all_tools():
    """Messaging resource should describe all messaging tools."""
    content = messaging_protocol.fn()
    for tool in [
        "brocode_send_message",
        "brocode_get_messages",
        "brocode_clear_messages",
    ]:
        assert tool in content, f"Messaging doc missing {tool}"
