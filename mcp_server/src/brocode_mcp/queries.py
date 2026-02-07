"""Cypher query constants for the broCode MCP server.

All queries match the schema defined in repo-graph/schema.example:
- Node labels: Codebase, Directory, File, Class, Function, Agent
- Relationship: (:Agent)-[:CLAIM {claim_reason}]->(:Codebase|Directory|File)
- Nodes use `codebase` property to scope to a specific repository.
- Codebase nodes are identified by `name`, others by `path` + `codebase`.

Queries are centralized here so they are easy to review, test, and change
without touching tool logic in server.py or DB logic in neo4j_client.py.
"""

# ===== CLAIM NODE =====

# Check if a node (File, Directory, or Codebase) exists for a given codebase.
# For Codebase nodes, node_path equals the codebase name.
CHECK_NODE_EXISTS = """
MATCH (n)
WHERE (n:Codebase AND n.name = $codebase AND $node_path = $codebase)
   OR ((n:File OR n:Directory) AND n.path = $node_path AND n.codebase = $codebase)
RETURN labels(n) AS labels, coalesce(n.path, n.name) AS path, n.name AS name
LIMIT 1
"""

# Check if a node is already claimed by any agent.
CHECK_EXISTING_CLAIM = """
MATCH (a:Agent)-[c:CLAIM]->(n)
WHERE (n:Codebase AND n.name = $codebase AND $node_path = $codebase)
   OR ((n:File OR n:Directory) AND n.path = $node_path AND n.codebase = $codebase)
RETURN a.name AS agent_name, a.model AS agent_model, c.claim_reason AS claim_reason
"""

# Create or merge the Agent node and the CLAIM relationship.
# Uses MERGE for idempotency — calling twice with same args is a no-op.
CREATE_CLAIM = """
MERGE (a:Agent {name: $agent_name})
SET a.model = $agent_model
WITH a
MATCH (n)
WHERE (n:Codebase AND n.name = $codebase AND $node_path = $codebase)
   OR ((n:File OR n:Directory) AND n.path = $node_path AND n.codebase = $codebase)
MERGE (a)-[c:CLAIM]->(n)
SET c.claim_reason = $claim_reason
RETURN labels(n) AS labels, coalesce(n.path, n.name) AS path, n.name AS name
"""

# ===== RELEASE NODE =====

# Remove a CLAIM relationship between a specific agent and a node.
# No longer returns root_path — reindexing is handled separately
# by brocode_update_graph.
RELEASE_CLAIM = """
MATCH (a:Agent {name: $agent_name})-[c:CLAIM]->(n)
WHERE (n:Codebase AND n.name = $codebase AND $node_path = $codebase)
   OR ((n:File OR n:Directory) AND n.path = $node_path AND n.codebase = $codebase)
DELETE c
RETURN a.name AS agent_name, labels(n) AS labels,
       coalesce(n.path, n.name) AS path
"""

# ===== GRAPH UPDATE: UPSERT =====

# Upsert a File node. MERGE on (path, codebase) for idempotency.
# When parent_path is non-empty, links to parent Directory via CONTAINS_FILE.
# When parent_path is empty (root-level file), links to the Codebase node.
UPSERT_FILE = """
MERGE (f:File {path: $path, codebase: $codebase})
SET f.name = $name, f.extension = $extension, f.size_bytes = $size_bytes
WITH f
CALL {
    WITH f
    WITH f WHERE $parent_path <> ''
    MATCH (d:Directory {path: $parent_path, codebase: $codebase})
    MERGE (d)-[:CONTAINS_FILE]->(f)
}
CALL {
    WITH f
    WITH f WHERE $parent_path = ''
    MATCH (cb:Codebase {name: $codebase})
    MERGE (cb)-[:CONTAINS_FILE]->(f)
}
RETURN f.path AS path
"""

# Upsert a Directory node. MERGE on (path, codebase) for idempotency.
# When parent_path is non-empty, links to parent Directory via CONTAINS_DIR.
# When parent_path is empty (top-level dir), links to the Codebase node.
UPSERT_DIRECTORY = """
MERGE (d:Directory {path: $path, codebase: $codebase})
SET d.name = $name, d.depth = $depth
WITH d
CALL {
    WITH d
    WITH d WHERE $parent_path <> ''
    MATCH (parent:Directory {path: $parent_path, codebase: $codebase})
    MERGE (parent)-[:CONTAINS_DIR]->(d)
}
CALL {
    WITH d
    WITH d WHERE $parent_path = ''
    MATCH (cb:Codebase {name: $codebase})
    MERGE (cb)-[:CONTAINS_DIR]->(d)
}
RETURN d.path AS path
"""

# Upsert a Function node. MERGE on (file_path, name, codebase) for idempotency.
# Links to parent File via DEFINES_FUNCTION edge (when File exists).
# If the function is a method (owner_class is set), also creates HAS_METHOD
# edge from the Class node to the Function.
UPSERT_FUNCTION = """
MERGE (fn:Function {file_path: $file_path, name: $name, codebase: $codebase})
SET fn.line_number = $line_number, fn.is_method = $is_method,
    fn.parameters = $parameters, fn.owner_class = $owner_class
WITH fn
OPTIONAL MATCH (f:File {path: $file_path, codebase: $codebase})
FOREACH (_ IN CASE WHEN f IS NOT NULL THEN [1] ELSE [] END |
    MERGE (f)-[:DEFINES_FUNCTION]->(fn)
)
WITH fn
CALL {
    WITH fn
    WITH fn WHERE $owner_class <> ''
    MATCH (cls:Class {file_path: $file_path, name: $owner_class, codebase: $codebase})
    MERGE (cls)-[:HAS_METHOD]->(fn)
}
RETURN fn.name AS name
"""

# Upsert a Class node. MERGE on (file_path, name, codebase) for idempotency.
# Links to parent File via DEFINES_CLASS edge (when File exists).
UPSERT_CLASS = """
MERGE (c:Class {file_path: $file_path, name: $name, codebase: $codebase})
SET c.line_number = $line_number, c.base_classes = $base_classes
WITH c
OPTIONAL MATCH (f:File {path: $file_path, codebase: $codebase})
FOREACH (_ IN CASE WHEN f IS NOT NULL THEN [1] ELSE [] END |
    MERGE (f)-[:DEFINES_CLASS]->(c)
)
RETURN c.name AS name
"""

# ===== GRAPH UPDATE: DELETE =====

# Delete a File node and its AST children (Function, Class).
DELETE_FILE = """
MATCH (f:File {path: $path, codebase: $codebase})
OPTIONAL MATCH (f)-[*]->(child)
DETACH DELETE child
WITH f
DETACH DELETE f
"""

# Delete a Directory node and all nodes reachable below it.
DELETE_DIRECTORY = """
MATCH (d:Directory {path: $path, codebase: $codebase})
OPTIONAL MATCH (d)-[*]->(descendant)
DETACH DELETE descendant
WITH d
DETACH DELETE d
"""

# Delete a specific Function node.
DELETE_FUNCTION = """
MATCH (fn:Function {file_path: $file_path, name: $name, codebase: $codebase})
DETACH DELETE fn
"""

# Delete a Class node and its methods (Functions with owner_class matching).
DELETE_CLASS = """
MATCH (c:Class {file_path: $file_path, name: $name, codebase: $codebase})
OPTIONAL MATCH (fn:Function {file_path: $file_path, owner_class: $name, codebase: $codebase})
DETACH DELETE fn
WITH c
DETACH DELETE c
"""

# ===== GET ACTIVE AGENTS =====

# Return all CLAIM relationships across all codebases.
GET_ACTIVE_AGENTS_ALL = """
MATCH (a:Agent)-[c:CLAIM]->(n)
RETURN a.name AS agent_name, a.model AS agent_model,
       labels(n) AS node_labels,
       coalesce(n.path, n.name) AS node_path,
       c.claim_reason AS claim_reason
ORDER BY a.name, node_path
"""

# Return CLAIM relationships filtered to a specific codebase.
GET_ACTIVE_AGENTS_BY_CODEBASE = """
MATCH (a:Agent)-[c:CLAIM]->(n)
WHERE (n:Codebase AND n.name = $codebase)
   OR ((n:File OR n:Directory) AND n.codebase = $codebase)
RETURN a.name AS agent_name, a.model AS agent_model,
       labels(n) AS node_labels,
       coalesce(n.path, n.name) AS node_path,
       c.claim_reason AS claim_reason
ORDER BY a.name, node_path
"""

# ===== QUERY CODEBASE =====

# Template for searching nodes with optional type filter and claim status.
# {type_clause} and {where_clause} are injected by neo4j_client.py after
# validating against an allowlist. $codebase and $limit remain parameterized.
# Neo4j does not support parameterized labels, so string formatting is required.
QUERY_CODEBASE_TEMPLATE = """
MATCH (n{type_clause})
WHERE {where_clause}
OPTIONAL MATCH (a:Agent)-[c:CLAIM]->(n)
RETURN labels(n) AS node_labels,
       coalesce(n.path, n.name) AS node_path,
       n.name AS node_name,
       a.name AS claimed_by,
       c.claim_reason AS claim_reason
ORDER BY node_path
LIMIT $limit
"""

# ===== MESSAGING =====

# Check if an Agent node exists by name.
CHECK_AGENT_EXISTS = """
MATCH (a:Agent {name: $agent_name})
RETURN a.name AS name, a.model AS model
LIMIT 1
"""

# Append a JSON-encoded message string to the target agent's messages list.
# Uses coalesce to initialize the list if it doesn't exist yet.
# Wraps $message in a list so Neo4j appends a single element (not char-by-char).
SEND_MESSAGE = """
MATCH (a:Agent {name: $to_agent})
SET a.messages = coalesce(a.messages, []) + [$message]
RETURN size(a.messages) AS message_count
"""

# Retrieve the messages list for an agent.
GET_MESSAGES = """
MATCH (a:Agent {name: $agent_name})
RETURN coalesce(a.messages, []) AS messages
"""

# Clear all messages for an agent after reading.
CLEAR_MESSAGES = """
MATCH (a:Agent {name: $agent_name})
SET a.messages = []
"""

# ===== AGENT CLEANUP =====

# Count remaining CLAIM relationships for an agent.
# Used after release to decide whether to delete the Agent node.
COUNT_AGENT_CLAIMS = """
MATCH (a:Agent {name: $agent_name})-[c:CLAIM]->()
RETURN count(c) AS claim_count
"""

# Delete an Agent node (only called when it has no remaining claims).
DELETE_AGENT = """
MATCH (a:Agent {name: $agent_name})
DETACH DELETE a
"""
