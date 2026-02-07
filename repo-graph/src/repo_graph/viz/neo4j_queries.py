"""Neo4j data layer for the broCode visualization.

Provides cached driver creation and three fetch functions that return
raw dicts (ready for the graph builder in app.py).  Uses the synchronous
Neo4j driver — Streamlit's execution model is synchronous and the queries
are fast enough that async adds no benefit here.

Environment variables (loaded from .env by app.py before import):
    NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE
"""

from __future__ import annotations

import os

import streamlit as st
from neo4j import GraphDatabase

# ---------------------------------------------------------------------------
# Cypher queries
# ---------------------------------------------------------------------------

LIST_CODEBASES = "MATCH (c:Codebase) RETURN c.name AS name ORDER BY name"

# Two-pattern UNION ALL: filesystem edges + AST edges.
# Returns node properties + edge endpoints using elementId().
FETCH_GRAPH = """
MATCH (c:Codebase {name: $codebase})-[r1]->(child)
RETURN
    elementId(child)   AS element_id,
    labels(child)      AS labels,
    child.name         AS name,
    child.path         AS path,
    elementId(c)       AS src_id,
    elementId(child)   AS tgt_id,
    type(r1)           AS rel_type,
    elementId(c)       AS cb_id,
    c.name             AS cb_name
UNION ALL
MATCH (c:Codebase {name: $codebase})-[*1..2]->(parent)-[r2]->(desc)
WHERE NOT parent:Codebase
RETURN
    elementId(desc)    AS element_id,
    labels(desc)       AS labels,
    desc.name          AS name,
    desc.path          AS path,
    elementId(parent)  AS src_id,
    elementId(desc)    AS tgt_id,
    type(r2)           AS rel_type,
    elementId(c)       AS cb_id,
    c.name             AS cb_name
"""

# Active claims: Agent -[:CLAIMS]-> node
FETCH_CLAIMS = """
MATCH (a:Agent)-[:CLAIMS]->(n)
WHERE n.codebase = $codebase OR n.name = $codebase
RETURN
    elementId(n)  AS element_id,
    a.name        AS agent_name,
    a.model       AS agent_model
"""

# ---------------------------------------------------------------------------
# Driver (cached for Streamlit reruns)
# ---------------------------------------------------------------------------


@st.cache_resource
def get_driver():
    """Create and cache a Neo4j driver from environment variables."""
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USERNAME", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "password")
    return GraphDatabase.driver(uri, auth=(user, password))


# ---------------------------------------------------------------------------
# Fetch helpers — no caching, we want fresh data every refresh cycle
# ---------------------------------------------------------------------------


def fetch_codebases() -> list[str]:
    """Return a list of all indexed codebase names."""
    driver = get_driver()
    with driver.session(database=os.environ.get("NEO4J_DATABASE", "neo4j")) as session:
        result = session.run(LIST_CODEBASES)
        return [record["name"] for record in result]


def fetch_graph(codebase: str) -> tuple[list[dict], list[dict]]:
    """Fetch all nodes and edges for a codebase.

    Returns (nodes_data, edges_data) where each item is a list of dicts.
    Nodes are deduplicated by element_id.  The Codebase root node is
    injected separately since the UNION query only returns children.
    """
    driver = get_driver()
    db = os.environ.get("NEO4J_DATABASE", "neo4j")
    with driver.session(database=db) as session:
        records = session.run(FETCH_GRAPH, codebase=codebase).data()

    # Deduplicate nodes by element_id
    seen_nodes: dict[str, dict] = {}
    edges: list[dict] = []

    for row in records:
        eid = row["element_id"]
        if eid not in seen_nodes:
            seen_nodes[eid] = {
                "n": {
                    "element_id": eid,
                    "labels": row["labels"],
                    "name": row["name"],
                    "path": row.get("path", ""),
                }
            }
        edges.append({
            "src_id": row["src_id"],
            "tgt_id": row["tgt_id"],
            "rel_type": row["rel_type"],
        })

    # Inject the Codebase root node
    if records:
        cb_id = records[0]["cb_id"]
        cb_name = records[0]["cb_name"]
        if cb_id not in seen_nodes:
            seen_nodes[cb_id] = {
                "n": {
                    "element_id": cb_id,
                    "labels": ["Codebase"],
                    "name": cb_name,
                    "path": "",
                }
            }

    # Deduplicate edges
    unique_edges: dict[tuple, dict] = {}
    for e in edges:
        key = (e["src_id"], e["tgt_id"], e["rel_type"])
        if key not in unique_edges:
            unique_edges[key] = e

    return list(seen_nodes.values()), list(unique_edges.values())


def fetch_claims(codebase: str) -> dict[str, dict]:
    """Fetch active agent claims for a codebase.

    Returns {element_id: {"agent_name": ..., "agent_model": ...}}.
    """
    driver = get_driver()
    db = os.environ.get("NEO4J_DATABASE", "neo4j")
    with driver.session(database=db) as session:
        records = session.run(FETCH_CLAIMS, codebase=codebase).data()

    claims: dict[str, dict] = {}
    for row in records:
        claims[row["element_id"]] = {
            "agent_name": row["agent_name"],
            "agent_model": row.get("agent_model", "unknown"),
        }
    return claims
