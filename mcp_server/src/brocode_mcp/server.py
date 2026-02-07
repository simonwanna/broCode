"""broCode MCP Server — multi-agent codebase coordination.

Provides four tools for AI agents to coordinate work on shared codebases:
- brocode_claim_node: Claim a file/directory you're working on
- brocode_release_node: Release a claimed node (optionally re-index)
- brocode_get_active_agents: See who is working where
- brocode_query_codebase: Search the codebase graph structure

Runs via stdio transport. The Neo4j async driver is initialized once at
startup via the lifespan and shared across all tool invocations.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator

from fastmcp import Context, FastMCP

from brocode_mcp.env import load_neo4j_config
from brocode_mcp.neo4j_client import Neo4jClient

# For stdio transport, never log to stdout — it corrupts the MCP protocol.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("brocode_mcp")


# ------------------------------------------------------------------
# Lifespan: create and tear down the Neo4j async driver once
# ------------------------------------------------------------------


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Initialize the Neo4j async driver at startup, close it on shutdown.

    The yielded dict is accessible in tools via _get_db(ctx), which reads
    ctx.request_context.lifespan_context["db"] (FastMCP >=2.3 API).
    """
    config = load_neo4j_config()
    db = Neo4jClient(config)
    logger.info(
        "Neo4j async driver initialized (uri=%s, database=%s)",
        config.uri,
        config.database,
    )
    try:
        yield {"db": db}
    finally:
        await db.close()
        logger.info("Neo4j async driver closed.")


# ------------------------------------------------------------------
# FastMCP server instance
# ------------------------------------------------------------------

mcp = FastMCP(
    "broCode",
    instructions=(
        "broCode coordinates multiple AI agents working on the same codebase. "
        "Use brocode_claim_node before editing files, brocode_release_node when "
        "done, brocode_get_active_agents to see who is working where, and "
        "brocode_query_codebase to explore the repository structure."
    ),
    lifespan=app_lifespan,
)

# Valid node types for query filtering — also used by neo4j_client.py
VALID_NODE_TYPES = {"File", "Directory", "Codebase", "Class", "Function"}



def _get_db(ctx: Context) -> Neo4jClient:
    """Extract the Neo4jClient from the FastMCP context.

    In FastMCP >=2.3 the lifespan dict moved from ctx.lifespan_context to
    ctx.request_context.lifespan_context.  This helper keeps tool code
    decoupled from that internal change.
    """
    return ctx.request_context.lifespan_context["db"]


# ===================================================================
# Tool 1: brocode_claim_node
# ===================================================================


@mcp.tool(
    annotations={
        "title": "Claim a codebase node",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def brocode_claim_node(
    agent_name: str,
    agent_model: str,
    node_path: str,
    codebase_name: str,
    claim_reason: str = "",
    ctx: Context = None,
) -> dict:
    """Claim a file or directory you are working on so other agents know not to touch it.

    Call this before editing a file. If another agent already holds the claim,
    you'll get a conflict response telling you who is working on it.

    Args:
        agent_name: Your agent identifier (e.g. "claude-session-1").
        agent_model: Model type (e.g. "claude", "gemini").
        node_path: Relative path of the file or directory to claim (e.g. "src/app.py").
        codebase_name: Name of the codebase (matches the Codebase node's name property).
        claim_reason: A free-text description of what you plan to do with this file (e.g. "Changes to input parameters and return statement"). Required — cannot be empty.

    Returns:
        A dict with "status" ("claimed", "already_yours", "conflict", "error").
    """
    db: Neo4jClient = _get_db(ctx)

    # Validate claim_reason is a non-empty description of planned work
    if not claim_reason or not claim_reason.strip():
        return {
            "status": "error",
            "message": (
                "claim_reason is required. Describe what you plan to do "
                "with this file (e.g. 'Changes to input parameters and return statement')."
            ),
        }

    # Step 1: Verify the node exists in the graph
    node = await db.check_node_exists(node_path, codebase_name)
    if node is None:
        return {
            "status": "error",
            "message": (
                f"Node '{node_path}' not found in codebase '{codebase_name}'. "
                "Has the repository been indexed?"
            ),
        }

    # Step 2: Check for existing claims
    claims = await db.check_existing_claim(node_path, codebase_name)
    for claim in claims:
        if claim["agent_name"] == agent_name:
            return {
                "status": "already_yours",
                "message": f"You ({agent_name}) already have this node claimed.",
                "node_path": node_path,
            }
        else:
            return {
                "status": "conflict",
                "message": (
                    f"CONFLICT: '{claim['agent_name']}' ({claim['agent_model']}) "
                    f"is currently working on '{node_path}'."
                ),
                "claimed_by": claim["agent_name"],
                "claim_reason": claim.get("claim_reason", ""),
            }

    # Step 3: Create the claim
    result = await db.create_claim(
        agent_name, agent_model, node_path, codebase_name, claim_reason
    )
    if result is None:
        return {"status": "error", "message": "Failed to create claim (unexpected)."}

    logger.info(
        "Agent '%s' claimed node '%s' in codebase '%s'",
        agent_name,
        node_path,
        codebase_name,
    )
    return {
        "status": "claimed",
        "message": f"Successfully claimed '{node_path}'.",
        "node_path": node_path,
        "agent_name": agent_name,
    }


# ===================================================================
# Tool 2: brocode_release_node
# ===================================================================


@mcp.tool(
    annotations={
        "title": "Release a claimed node and reindex",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def brocode_release_node(
    agent_name: str,
    node_path: str,
    codebase_name: str,
    ctx: Context = None,
) -> dict:
    """Release a file or directory you previously claimed and reindex it.

    Call this when you're done working on a node. The subtree rooted at
    node_path is cleared from the graph and re-indexed from the filesystem
    so the graph reflects any changes you made.

    The repo root path is resolved automatically from the Codebase node's
    root_path property (set during initial indexing).

    Args:
        agent_name: Your agent identifier.
        node_path: Relative path of the node to release.
        codebase_name: Name of the codebase.

    Returns:
        A dict with "status" ("released", "not_found") and reindex info.
    """
    db: Neo4jClient = _get_db(ctx)

    result = await db.release_claim(agent_name, node_path, codebase_name)
    if result is None:
        return {
            "status": "not_found",
            "message": f"No claim by '{agent_name}' on '{node_path}' was found.",
        }

    node_labels = result.get("labels", [])
    root_path = result.get("root_path", "")
    is_directory = "Directory" in node_labels

    logger.info(
        "Agent '%s' released node '%s' in codebase '%s'",
        agent_name,
        node_path,
        codebase_name,
    )
    response: dict = {
        "status": "released",
        "message": f"Released '{node_path}'.",
        "node_path": node_path,
        "agent_name": agent_name,
    }

    # Reindex: clear stale data from Neo4j, then re-run the indexer
    # in-process so the graph reflects any filesystem changes the agent made.
    if not root_path:
        response["reindex_status"] = "skipped"
        response["reindex_message"] = (
            "Codebase root_path not found in graph. "
            "Re-run the full indexer to set it."
        )
        return response

    # Step 1: Clear the subtree from Neo4j
    await db.clear_subtree(node_path, codebase_name, is_directory)
    logger.info("Cleared subtree '%s' from graph", node_path)

    # Step 2: Re-index the subtree.  index_repository and Neo4jStore are
    # synchronous, so we run them in a thread to avoid blocking the event loop.
    # We scope the reindex to the released subtree (directory or file's parent)
    # rather than re-indexing the entire repo.
    try:
        reindex_msg = await asyncio.to_thread(
            _reindex_sync, root_path, node_path, codebase_name, is_directory
        )
        response["reindex_status"] = "success"
        response["reindex_message"] = reindex_msg
    except Exception as exc:
        logger.error("Reindex failed for '%s': %s", node_path, exc)
        response["reindex_status"] = "error"
        response["reindex_message"] = str(exc)

    return response


def _reindex_sync(
    root_path: str,
    node_path: str,
    codebase_name: str,
    is_directory: bool,
) -> str:
    """Re-index the released subtree (called via asyncio.to_thread).

    Scopes the reindex to just the released node's subtree:
    - Directory release: indexes that directory
    - File release: indexes the file's parent directory

    The codebase name is preserved so nodes keep the correct ``codebase``
    property and edges reconnect to the existing graph via MERGE.

    Imports repo_graph inline so the MCP server only needs it installed
    at reindex time, not at startup.
    """
    import os
    from pathlib import Path

    from repo_graph.indexer.filesystem import index_repository
    from repo_graph.storage.neo4j_store import Neo4jStore

    repo_root = Path(root_path)
    if not repo_root.is_dir():
        raise FileNotFoundError(f"Repo root '{root_path}' is not a directory")

    # Determine the subtree to reindex
    if is_directory:
        subtree = repo_root / node_path
    else:
        # For a file, reindex its parent directory
        subtree = repo_root / Path(node_path).parent
        # If the file was at the repo root (no parent), reindex the repo root
        if subtree == repo_root / ".":
            subtree = repo_root

    if not subtree.is_dir():
        # Subtree was deleted from filesystem — nothing to reindex
        return f"Subtree '{node_path}' no longer exists on disk, skipped reindex"

    result = index_repository(subtree, analyze_python=True)

    # Override the codebase name so nodes merge into the existing graph
    # (index_repository would set it to subtree.name, e.g. "app" instead
    # of "demo-api").
    result.codebase.name = codebase_name
    result.codebase.root_path = root_path
    for d in result.directories:
        d.path = str(Path(node_path if is_directory else str(Path(node_path).parent)) / d.path)
    for f in result.files:
        f.path = str(Path(node_path if is_directory else str(Path(node_path).parent)) / f.path)
    for e in result.edges:
        # Fix edge source/target paths — skip the codebase root reference
        if e.source_path == subtree.name:
            e.source_path = codebase_name
        else:
            prefix = node_path if is_directory else str(Path(node_path).parent)
            if prefix and prefix != ".":
                e.source_path = str(Path(prefix) / e.source_path)
        # Target paths
        if e.target_path != codebase_name:
            prefix = node_path if is_directory else str(Path(node_path).parent)
            if prefix and prefix != ".":
                e.target_path = str(Path(prefix) / e.target_path)

    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USERNAME", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "password")
    database = os.environ.get("NEO4J_DATABASE", "neo4j")

    with Neo4jStore(uri, user, password, database) as store:
        store.save(result)

    return (
        f"Reindexed '{node_path}': "
        f"{len(result.directories)} dirs, {len(result.files)} files, "
        f"{len(result.functions)} functions, {len(result.classes)} classes"
    )


# ===================================================================
# Tool 3: brocode_get_active_agents
# ===================================================================


@mcp.tool(
    annotations={
        "title": "Get active agents",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def brocode_get_active_agents(
    codebase_name: str = "",
    ctx: Context = None,
) -> dict:
    """Query which agents are currently working on which files/directories.

    Use this to check for potential conflicts before starting work, or to
    get an overview of all active agents across codebases.

    Args:
        codebase_name: Filter by codebase name. If empty, returns all claims.

    Returns:
        A dict with "agents": list of agent records, each with their claims.
    """
    db: Neo4jClient = _get_db(ctx)

    codebase = codebase_name if codebase_name else None
    records = await db.get_active_agents(codebase)

    # Group by agent for a cleaner response
    agents: dict[str, dict] = {}
    for rec in records:
        name = rec["agent_name"]
        if name not in agents:
            agents[name] = {
                "agent_name": name,
                "agent_model": rec["agent_model"],
                "claims": [],
            }
        # Extract primary node type from labels list
        node_labels = rec.get("node_labels", [])
        primary_type = next(
            (l for l in node_labels if l in VALID_NODE_TYPES),
            "Unknown",
        )
        agents[name]["claims"].append(
            {
                "node_path": rec["node_path"],
                "node_type": primary_type,
                "claim_reason": rec.get("claim_reason", ""),
            }
        )

    return {
        "status": "ok",
        "agent_count": len(agents),
        "agents": list(agents.values()),
    }


# ===================================================================
# Tool 4: brocode_query_codebase
# ===================================================================


@mcp.tool(
    annotations={
        "title": "Query codebase structure",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def brocode_query_codebase(
    codebase_name: str,
    path_filter: str = "",
    node_type: str = "",
    limit: int = 50,
    ctx: Context = None,
) -> dict:
    """Search the indexed codebase structure and see which nodes are claimed.

    Use this to explore the repository graph, find files matching a pattern,
    or check the claim status of specific paths.

    Args:
        codebase_name: Name of the codebase to search.
        path_filter: Optional glob pattern to filter paths (e.g. "src/*.py").
        node_type: Optional filter: "File", "Directory", "Codebase", "Class", or "Function".
        limit: Maximum results to return (default 50, max 200).

    Returns:
        A dict with "nodes": list of matching nodes and their claim status.
    """
    db: Neo4jClient = _get_db(ctx)

    # Validate node_type
    if node_type and node_type not in VALID_NODE_TYPES:
        return {
            "status": "error",
            "message": (
                f"Invalid node_type '{node_type}'. "
                f"Must be one of: {', '.join(sorted(VALID_NODE_TYPES))}"
            ),
        }

    # Clamp limit
    limit = max(1, min(limit, 200))

    records = await db.query_codebase(
        codebase=codebase_name,
        path_filter=path_filter if path_filter else None,
        node_type=node_type if node_type else None,
        limit=limit,
    )

    nodes = []
    for rec in records:
        node_labels = rec.get("node_labels", [])
        primary_type = next(
            (l for l in node_labels if l in VALID_NODE_TYPES),
            "Unknown",
        )
        nodes.append(
            {
                "path": rec["node_path"],
                "name": rec.get("node_name", ""),
                "type": primary_type,
                "claimed_by": rec.get("claimed_by"),
                "claim_reason": rec.get("claim_reason"),
            }
        )

    return {
        "status": "ok",
        "count": len(nodes),
        "codebase": codebase_name,
        "nodes": nodes,
    }


# ===================================================================
# Tool 5: brocode_send_message
# ===================================================================


@mcp.tool(
    annotations={
        "title": "Send a message to another agent",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    }
)
async def brocode_send_message(
    from_agent: str,
    to_agent: str,
    message: str,
    node_path: str = "",
    ctx: Context = None,
) -> dict:
    """Send a message to another active agent.

    Use this when another agent has claimed a node you need access to,
    or to coordinate work. Messages are stored on the recipient's Agent
    node and retrieved when they call brocode_get_messages.

    Args:
        from_agent: Your agent identifier (the sender).
        to_agent: The recipient agent's name.
        message: Free-text message content describing your request.
        node_path: Optional path of the node this message is about.

    Returns:
        A dict with "status" ("sent", "error") and delivery info.
    """
    db: Neo4jClient = _get_db(ctx)

    # Validate: no self-messaging
    if from_agent == to_agent:
        return {
            "status": "error",
            "message": "Cannot send a message to yourself.",
        }

    # Validate: message must be non-empty
    if not message or not message.strip():
        return {
            "status": "error",
            "message": "Message content is required and cannot be empty.",
        }

    # Validate: target agent must exist
    agent = await db.check_agent_exists(to_agent)
    if agent is None:
        return {
            "status": "error",
            "message": f"Agent '{to_agent}' not found. Has it registered by claiming a node?",
        }

    # Build the message payload
    msg_dict = {
        "from": from_agent,
        "content": message,
        "node_path": node_path,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    msg_json = json.dumps(msg_dict)

    result = await db.send_message(to_agent, msg_json)
    if result is None:
        return {"status": "error", "message": "Failed to deliver message (unexpected)."}

    logger.info(
        "Agent '%s' sent message to '%s' (re: '%s')",
        from_agent,
        to_agent,
        node_path or "general",
    )
    return {
        "status": "sent",
        "to_agent": to_agent,
        "message_count": result["message_count"],
    }


# ===================================================================
# Tool 6: brocode_get_messages
# ===================================================================


@mcp.tool(
    annotations={
        "title": "Get messages for an agent",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    }
)
async def brocode_get_messages(
    agent_name: str,
    ctx: Context = None,
) -> dict:
    """Retrieve and clear messages for an agent (inbox model).

    Call this periodically to check if other agents have sent you
    messages (e.g., requesting access to a node you've claimed).
    Messages are cleared after reading.

    Args:
        agent_name: Your agent identifier.

    Returns:
        A dict with "status", "messages" (list of parsed message dicts),
        and "count".
    """
    db: Neo4jClient = _get_db(ctx)

    raw_messages = await db.get_messages(agent_name)

    # Parse JSON strings back to dicts
    messages = []
    for raw in raw_messages:
        try:
            messages.append(json.loads(raw))
        except (json.JSONDecodeError, TypeError):
            # Tolerate malformed entries — include raw string as content
            messages.append({"from": "unknown", "content": raw, "node_path": "", "timestamp": ""})

    # Clear inbox after reading (only if there were messages)
    if messages:
        await db.clear_messages(agent_name)

    return {
        "status": "ok",
        "messages": messages,
        "count": len(messages),
    }


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------


def main():
    """Run the MCP server with stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
