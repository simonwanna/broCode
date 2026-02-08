"""broCode MCP Server — multi-agent codebase coordination.

Provides tools for AI agents to coordinate work on shared codebases:
- brocode_claim_node: Claim a file/directory you're working on
- brocode_release_node: Release a claimed node
- brocode_update_graph: Apply per-node graph updates (upsert/delete)
- brocode_get_active_agents: See who is working where
- brocode_query_codebase: Search the codebase graph structure
- brocode_send_message / brocode_get_messages / brocode_clear_messages

Runs via stdio transport. The Neo4j async driver is initialized once at
startup via the lifespan and shared across all tool invocations.
"""

from __future__ import annotations

import json
import logging
import os
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


# ===================================================================
# MCP Resources — static reference documents for agents
# ===================================================================


@mcp.resource("brocode://agent-workflow")
def agent_workflow() -> str:
    """Standard workflow for agents using brocode."""
    return """\
# broCode Agent Workflow

Follow this lifecycle every time you work on a codebase managed by broCode.

## Step-by-step

1. **Check activity** — Call `brocode_get_active_agents` to see which agents
   are working where. This avoids conflicts before you even start.

2. **Explore the graph** — Call `brocode_query_codebase` to find the node(s)
   you need. Use `path_filter` globs and `node_type` to narrow results.

3. **Claim before editing** — Call `brocode_claim_node` for every file you intend to modify. Handle responses:
   - `claimed` — you now own the node; proceed.
   - `already_yours` — you already claimed it; proceed.
   - `conflict` — another agent owns it. Use `brocode_send_message` to
     negotiate, or pick a different file.


4. **Do your work** — Edit files, run tests, etc.

5. **Repeat** If you want to edit more files and nodes, repeat steps 2-4.

6. **Update the graph** — If you created, renamed, or deleted files,
   functions, or classes, call `brocode_update_graph` so the knowledge graph
   stays in sync. See the `brocode://update-graph-examples` resource for
   concrete JSON payloads. The graph should always reflect the current state
   of the codebase.

7. **Poll messages** — Call `brocode_get_messages` to see if another agent
   has sent a feature request. Handle responses:
   - `message` — another agent has requested access to a node you claimed.
     Use `brocode_send_message` to respond when the node is available.

8. **Release when done** — Call `brocode_release_node` for each node you
   claimed. The Agent node is automatically deleted when its last claim is
   released.

## Key rules

- **Always claim before editing.** Other agents rely on claims to avoid
  conflicts.
- **Always update the graph** if you changed files. Stale graphs cause
  confusion for the next agent.
- **Check for conflicts** before claiming — `brocode_get_active_agents` is
  cheap and saves time.
- **Poll messages** periodically while holding claims — another agent may
  need access. Use `brocode_get_messages` and `brocode_clear_messages`.
"""


@mcp.resource("brocode://graph-schema")
def graph_schema() -> str:
    """Node types, properties, and relationships in the brocode graph."""
    return """\
# broCode Graph Schema

## Node types and properties

### Codebase
- `name` — unique identifier (e.g. "broCode")
- `root_path` — absolute path on disk

### Directory
- `path` — relative path (e.g. "src/utils")
- `name` — directory name
- `depth` — nesting level from root
- `codebase` — owning codebase name

### File
- `path` — relative path (e.g. "src/app.py")
- `name` — file name
- `extension` — e.g. ".py"
- `size_bytes` — file size
- `codebase` — owning codebase name

### Function
- `file_path` — path of the containing file
- `name` — function name
- `line_number` — line where the function is defined
- `is_method` — true if it belongs to a class
- `parameters` — parameter signature string
- `owner_class` — class name (if is_method is true)
- `codebase` — owning codebase name

### Class
- `file_path` — path of the containing file
- `name` — class name
- `line_number` — line where the class is defined
- `base_classes` — comma-separated base class names
- `codebase` — owning codebase name

### Agent
- `name` — unique agent identifier (e.g. "claude-session-1")
- `model` — model type (e.g. "claude", "gemini")
- `messages` — JSON array of inbox messages

## Relationships

```
(Codebase)-[:CONTAINS_DIR]->(Directory)       # top-level dirs
(Codebase)-[:CONTAINS_FILE]->(File)           # root-level files
(Directory)-[:CONTAINS_DIR]->(Directory)      # nested dirs
(Directory)-[:CONTAINS_FILE]->(File)          # files in dir
(File)-[:DEFINES_FUNCTION]->(Function)        # standalone functions
(File)-[:DEFINES_CLASS]->(Class)              # class definitions
(Class)-[:HAS_METHOD]->(Function)             # methods on a class
(Agent)-[:CLAIM {claim_reason}]->(node)       # node = Codebase|Directory|File
```

The `CLAIM` relationship carries a `claim_reason` property describing the
agent's planned work.
"""


@mcp.resource("brocode://update-graph-examples")
def update_graph_examples() -> str:
    """Concrete JSON examples for brocode_update_graph."""
    return """\
# brocode_update_graph — Examples

All examples show the `changes` parameter passed to `brocode_update_graph`.

## Upsert a file

```json
[{"action": "upsert", "node_type": "File", "path": "src/utils/helpers.py"}]
```

With optional fields:
```json
[{
  "action": "upsert",
  "node_type": "File",
  "path": "src/utils/helpers.py",
  "name": "helpers.py",
  "extension": ".py",
  "size_bytes": 1234,
  "parent_path": "src/utils"
}]
```

## Upsert a directory

```json
[{"action": "upsert", "node_type": "Directory", "path": "src/utils"}]
```

With optional fields:
```json
[{
  "action": "upsert",
  "node_type": "Directory",
  "path": "src/utils",
  "name": "utils",
  "depth": 2,
  "parent_path": "src"
}]
```

## Upsert a function (standalone)

```json
[{
  "action": "upsert",
  "node_type": "Function",
  "file_path": "src/app.py",
  "function_name": "handle_request",
  "line_number": 42,
  "is_method": false,
  "parameters": "request, timeout=30"
}]
```

## Upsert a method (belongs to a class)

```json
[{
  "action": "upsert",
  "node_type": "Function",
  "file_path": "src/app.py",
  "function_name": "process",
  "line_number": 55,
  "is_method": true,
  "parameters": "self, data",
  "owner_class": "RequestHandler"
}]
```

## Upsert a class

```json
[{
  "action": "upsert",
  "node_type": "Class",
  "file_path": "src/app.py",
  "class_name": "RequestHandler",
  "line_number": 10,
  "base_classes": "BaseHandler, LoggingMixin"
}]
```

## Delete a file

```json
[{"action": "delete", "node_type": "File", "path": "src/old_module.py"}]
```

## Delete a directory

```json
[{"action": "delete", "node_type": "Directory", "path": "src/deprecated"}]
```

## Delete a function

```json
[{"action": "delete", "node_type": "Function", "file_path": "src/app.py", "function_name": "old_handler"}]
```

## Delete a class

```json
[{"action": "delete", "node_type": "Class", "file_path": "src/app.py", "class_name": "LegacyHandler"}]
```

## Batch: multiple changes in one call

```json
[
  {"action": "upsert", "node_type": "Directory", "path": "src/new_pkg"},
  {"action": "upsert", "node_type": "File", "path": "src/new_pkg/__init__.py"},
  {"action": "upsert", "node_type": "File", "path": "src/new_pkg/core.py"},
  {"action": "upsert", "node_type": "Class", "file_path": "src/new_pkg/core.py", "class_name": "Engine", "line_number": 1},
  {"action": "delete", "node_type": "File", "path": "src/old_module.py"}
]
```

## Partial failure response

If some changes succeed and others fail, you get status `"partial"`:

```json
{
  "status": "partial",
  "applied": 3,
  "errors": ["Change 2: missing required field 'path' for upsert File."]
}
```
"""


@mcp.resource("brocode://messaging")
def messaging_protocol() -> str:
    """When and how to use the brocode messaging tools."""
    return """\
# broCode Messaging Protocol

Agents can send messages to each other via the Agent node's inbox.
This is useful for negotiating access to claimed nodes.

## Tools

### brocode_send_message
Send a message to another agent.

Parameters:
- `from_agent` — your agent identifier
- `to_agent` — the recipient's agent identifier
- `message` — free-text content describing your request
- `node_path` (optional) — the node the message is about

### brocode_get_messages
Retrieve your inbox. Returns a list of message dicts, each with:
- `from` — sender agent name
- `content` — message text
- `node_path` — related node (may be empty)
- `timestamp` — ISO 8601 UTC timestamp

### brocode_clear_messages
Clear your inbox after processing messages. Safe to call on an empty inbox.

## Conventions

- **Include `node_path`** when your message is about a specific file or
  directory. This helps the recipient understand the context without
  guessing.
- **No self-messaging** — `from_agent` and `to_agent` must differ.
- **Poll periodically** — while you hold claims, call `brocode_get_messages`
  every few steps so you notice requests promptly.
- **Clear after reading** — call `brocode_clear_messages` once you have
  processed your inbox to keep it clean.

## Typical flow

1. You try to claim `src/app.py` but get a `conflict` — agent "gemini-1"
   owns it.
2. Call `brocode_send_message(from_agent="claude-1", to_agent="gemini-1",
   message="I need to update the import block in src/app.py — can you
   release it when you're done?", node_path="src/app.py")`.
3. Continue working on other files.
4. Later, call `brocode_get_messages` to check if gemini-1 responded.
5. Once gemini-1 releases the node, claim it and proceed.
"""


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
        "title": "Release a claimed node",
        "readOnlyHint": False,
        "destructiveHint": False,
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
    """Release a file or directory you previously claimed.

    Call this when you're done working on a node. The claim is removed
    so other agents can work on it. If you changed the file, use
    brocode_update_graph to update the graph before or after releasing.

    The Agent node is automatically deleted when it has no remaining claims.

    Args:
        agent_name: Your agent identifier.
        node_path: Relative path of the node to release.
        codebase_name: Name of the codebase.

    Returns:
        A dict with "status" ("released", "not_found") and release info.
    """
    db: Neo4jClient = _get_db(ctx)

    result = await db.release_claim(agent_name, node_path, codebase_name)
    if result is None:
        return {
            "status": "not_found",
            "message": f"No claim by '{agent_name}' on '{node_path}' was found.",
        }

    logger.info(
        "Agent '%s' released node '%s' in codebase '%s'",
        agent_name,
        node_path,
        codebase_name,
    )

    # Clean up Agent node if it has no remaining claims
    remaining = await db.count_agent_claims(agent_name)
    if remaining == 0:
        await db.delete_agent(agent_name)
        logger.info("Deleted Agent node '%s' (no remaining claims)", agent_name)

    return {
        "status": "released",
        "message": f"Released '{node_path}'.",
        "node_path": node_path,
        "agent_name": agent_name,
    }


# ===================================================================
# Tool 3: brocode_update_graph
# ===================================================================


# Valid node types that brocode_update_graph accepts for changes.
_UPDATE_NODE_TYPES = {"File", "Directory", "Function", "Class"}
_UPDATE_ACTIONS = {"upsert", "delete"}

# Required fields per (action, node_type) pair.
_REQUIRED_FIELDS: dict[tuple[str, str], list[str]] = {
    ("upsert", "File"): ["path"],
    ("upsert", "Directory"): ["path"],
    ("upsert", "Function"): ["file_path", "function_name"],
    ("upsert", "Class"): ["file_path", "class_name"],
    ("delete", "File"): ["path"],
    ("delete", "Directory"): ["path"],
    ("delete", "Function"): ["file_path", "function_name"],
    ("delete", "Class"): ["file_path", "class_name"],
}


@mcp.tool(
    annotations={
        "title": "Update codebase graph nodes",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def brocode_update_graph(
    codebase_name: str,
    changes: list[dict],
    ctx: Context = None,
) -> dict:
    """Apply per-node graph updates (upsert or delete) directly to Neo4j.

    Use this to keep the knowledge graph in sync after editing files.
    Each change dict specifies an action and a node type with its fields.

    Partial success model — if one change fails, the rest still apply.

    Args:
        codebase_name: Name of the codebase to update.
        changes: List of change dicts, each with:
            - action: "upsert" or "delete"
            - node_type: "File", "Directory", "Function", or "Class"
            - For File/Directory: "path" (required), optionally "name",
              "extension", "size_bytes", "depth", "parent_path"
            - For Function: "file_path" + "function_name" (required),
              optionally "line_number", "is_method", "parameters", "owner_class"
            - For Class: "file_path" + "class_name" (required),
              optionally "line_number", "base_classes"

    Returns:
        A dict with "status" ("ok", "partial", "error"),
        "applied" count, and "errors" list.
    """
    # Top-level validation
    if not codebase_name or not codebase_name.strip():
        return {"status": "error", "message": "codebase_name is required."}
    if not changes:
        return {
            "status": "error",
            "message": "changes list is required and cannot be empty.",
        }

    db: Neo4jClient = _get_db(ctx)
    applied = 0
    errors: list[str] = []

    for i, change in enumerate(changes):
        try:
            _apply_single_change(change, i)  # validate
            await _dispatch_change(db, codebase_name, change)
            applied += 1
        except ValueError as exc:
            errors.append(str(exc))
        except Exception as exc:
            errors.append(f"Change {i}: {exc}")

    if not errors:
        status = "ok"
    elif applied > 0:
        status = "partial"
    else:
        status = "error"

    return {"status": status, "applied": applied, "errors": errors}


def _apply_single_change(change: dict, index: int) -> None:
    """Validate a single change dict. Raises ValueError on problems."""
    action = change.get("action")
    if not action:
        raise ValueError(f"Change {index}: missing required field 'action'.")
    if action not in _UPDATE_ACTIONS:
        raise ValueError(
            f"Change {index}: invalid action '{action}'. "
            f"Must be one of: {', '.join(sorted(_UPDATE_ACTIONS))}."
        )

    node_type = change.get("node_type")
    if not node_type:
        raise ValueError(f"Change {index}: missing required field 'node_type'.")
    if node_type not in _UPDATE_NODE_TYPES:
        raise ValueError(
            f"Change {index}: invalid node_type '{node_type}'. "
            f"Must be one of: {', '.join(sorted(_UPDATE_NODE_TYPES))}."
        )

    required = _REQUIRED_FIELDS.get((action, node_type), [])
    for field in required:
        if not change.get(field):
            raise ValueError(
                f"Change {index}: missing required field '{field}' "
                f"for {action} {node_type}."
            )


async def _dispatch_change(db: Neo4jClient, codebase: str, change: dict) -> None:
    """Dispatch a validated change to the appropriate DB method."""
    action = change["action"]
    node_type = change["node_type"]

    if action == "upsert":
        if node_type == "File":
            path = change["path"]
            name = change.get("name") or os.path.basename(path)
            extension = change.get("extension") or os.path.splitext(path)[1]
            await db.upsert_file(
                codebase=codebase,
                path=path,
                name=name,
                extension=extension,
                size_bytes=change.get("size_bytes", 0),
                parent_path=change.get("parent_path", ""),
            )
        elif node_type == "Directory":
            path = change["path"]
            name = change.get("name") or os.path.basename(path)
            await db.upsert_directory(
                codebase=codebase,
                path=path,
                name=name,
                depth=change.get("depth", 0),
                parent_path=change.get("parent_path", ""),
            )
        elif node_type == "Function":
            await db.upsert_function(
                codebase=codebase,
                file_path=change["file_path"],
                name=change["function_name"],
                line_number=change.get("line_number", 0),
                is_method=change.get("is_method", False),
                parameters=change.get("parameters", ""),
                owner_class=change.get("owner_class", ""),
            )
        elif node_type == "Class":
            await db.upsert_class(
                codebase=codebase,
                file_path=change["file_path"],
                name=change["class_name"],
                line_number=change.get("line_number", 0),
                base_classes=change.get("base_classes", ""),
            )

    elif action == "delete":
        if node_type == "File":
            await db.delete_file(path=change["path"], codebase=codebase)
        elif node_type == "Directory":
            await db.delete_directory(path=change["path"], codebase=codebase)
        elif node_type == "Function":
            await db.delete_function(
                file_path=change["file_path"],
                name=change["function_name"],
                codebase=codebase,
            )
        elif node_type == "Class":
            await db.delete_class(
                file_path=change["file_path"],
                name=change["class_name"],
                codebase=codebase,
            )


# ===================================================================
# Tool 4: brocode_get_active_agents
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
    """Retrieve messages for an agent.

    Call this periodically to check if other agents have sent you
    messages (e.g., requesting access to a node you've claimed).
    Use brocode_clear_messages to delete messages after processing them.

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
            messages.append(
                {"from": "unknown", "content": raw, "node_path": "", "timestamp": ""}
            )

    return {
        "status": "ok",
        "messages": messages,
        "count": len(messages),
    }


# ===================================================================
# Tool 7: brocode_clear_messages
# ===================================================================


@mcp.tool(
    annotations={
        "title": "Clear messages for an agent",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def brocode_clear_messages(
    agent_name: str,
    ctx: Context = None,
) -> dict:
    """Clear all messages for an agent after reading them.

    Call this after retrieving messages with brocode_get_messages
    and processing them. Safe to call on an empty inbox.

    Args:
        agent_name: Your agent identifier.

    Returns:
        A dict with "status" ("ok").
    """
    db: Neo4jClient = _get_db(ctx)

    await db.clear_messages(agent_name)

    logger.info("Cleared messages for agent '%s'", agent_name)
    return {"status": "ok", "message": f"Messages cleared for '{agent_name}'."}


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------


def main():
    """Run the MCP server with stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
