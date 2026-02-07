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

# Remove a CLAIM relationship between a specific agent and a node,
# and return the Codebase root_path so the caller can resolve the
# absolute filesystem path for reindexing.
RELEASE_CLAIM = """
MATCH (a:Agent {name: $agent_name})-[c:CLAIM]->(n)
WHERE (n:Codebase AND n.name = $codebase AND $node_path = $codebase)
   OR ((n:File OR n:Directory) AND n.path = $node_path AND n.codebase = $codebase)
DELETE c
WITH a, n
OPTIONAL MATCH (cb:Codebase {name: $codebase})
RETURN a.name AS agent_name, labels(n) AS labels,
       coalesce(n.path, n.name) AS path, cb.root_path AS root_path
"""

# ===== REINDEX SUBTREE =====

# Delete a Directory node and all nodes reachable below it (child dirs,
# files, and their AST children like Class/Function), then remove
# dangling relationships.  Preserves CLAIM edges on the directory itself
# (those are deleted separately by RELEASE_CLAIM).
CLEAR_SUBTREE_DIR = """
MATCH (d:Directory {path: $node_path, codebase: $codebase})
OPTIONAL MATCH (d)-[*]->(descendant)
DETACH DELETE descendant
WITH d
DETACH DELETE d
"""

# Delete a single File node and its AST children (Function, Class).
CLEAR_SUBTREE_FILE = """
MATCH (f:File {path: $node_path, codebase: $codebase})
OPTIONAL MATCH (f)-[*]->(child)
DETACH DELETE child
WITH f
DETACH DELETE f
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
