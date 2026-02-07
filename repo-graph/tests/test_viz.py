"""Tests for the Streamlit visualization helpers.

These tests exercise the pure-logic functions in viz/app.py (graph building,
color resolution, type mapping) WITHOUT requiring a running Neo4j instance or
Streamlit server.  All Neo4j data is supplied as plain dicts, mimicking the
shape returned by the driver's `.data()` method.
"""

from __future__ import annotations

import pytest

# Functions under test — imported from the app module so they can be
# exercised in isolation.  The app module guards Streamlit imports behind
# `if __name__` / the `main()` entry-point, so importing these helpers
# does NOT require Streamlit to be installed in the test environment.
from repo_graph.viz.app import (
    AGENT_COLORS,
    NODE_COLORS,
    agent_color,
    build_agraph,
    primary_type,
)


# -------------------------------------------------------------------
# primary_type — maps a Neo4j label list to a single canonical type
# -------------------------------------------------------------------

class TestPrimaryType:
    """Resolve a list of Neo4j labels to the single type we care about."""

    def test_single_known_label(self):
        assert primary_type(["File"]) == "File"

    def test_multiple_labels_picks_priority(self):
        # Neo4j nodes can carry multiple labels; we want the most specific.
        assert primary_type(["Codebase", "Node"]) == "Codebase"

    def test_directory_label(self):
        assert primary_type(["Directory"]) == "Directory"

    def test_class_and_function(self):
        assert primary_type(["Class"]) == "Class"
        assert primary_type(["Function"]) == "Function"

    def test_unknown_label_falls_back(self):
        assert primary_type(["SomethingElse"]) == "Unknown"

    def test_empty_labels(self):
        assert primary_type([]) == "Unknown"


# -------------------------------------------------------------------
# agent_color — pick a highlight color for a claiming agent
# -------------------------------------------------------------------

class TestAgentColor:
    """Look up the display color for an agent model."""

    def test_known_model_claude(self):
        assert agent_color("claude") == AGENT_COLORS["claude"]

    def test_known_model_gemini(self):
        assert agent_color("gemini") == AGENT_COLORS["gemini"]

    def test_unknown_model_gets_default(self):
        # Unknown agent models should still get a visible color.
        color = agent_color("gpt-5")
        assert isinstance(color, str)
        assert color.startswith("#")


# -------------------------------------------------------------------
# build_agraph — turn raw Neo4j rows into streamlit-agraph nodes/edges
# -------------------------------------------------------------------

def _make_node(element_id: str, labels: list[str], name: str, path: str = "") -> dict:
    """Helper to build a fake Neo4j node record."""
    return {
        "n": {
            "element_id": element_id,
            "labels": labels,
            "name": name,
            "path": path,
        }
    }


def _make_edge(src_id: str, tgt_id: str, rel_type: str) -> dict:
    return {
        "src_id": src_id,
        "tgt_id": tgt_id,
        "rel_type": rel_type,
    }


class TestBuildGraphNoClaims:
    """Graph construction without any active agent claims."""

    def test_basic_tree(self):
        nodes_data = [
            _make_node("1", ["Codebase"], "myrepo"),
            _make_node("2", ["Directory"], "src", path="src"),
            _make_node("3", ["File"], "app.py", path="src/app.py"),
        ]
        edges_data = [
            _make_edge("1", "2", "CONTAINS_DIR"),
            _make_edge("2", "3", "CONTAINS_FILE"),
        ]

        ag_nodes, ag_edges = build_agraph(nodes_data, edges_data, claims={})

        assert len(ag_nodes) == 3
        assert len(ag_edges) == 2

        # Verify node colors match their types
        codebase_node = next(n for n in ag_nodes if n.id == "1")
        assert codebase_node.color == NODE_COLORS["Codebase"]

        file_node = next(n for n in ag_nodes if n.id == "3")
        assert file_node.color == NODE_COLORS["File"]

    def test_empty_graph(self):
        ag_nodes, ag_edges = build_agraph([], [], claims={})
        assert ag_nodes == []
        assert ag_edges == []


class TestBuildGraphWithClaims:
    """Claimed nodes should be highlighted with the agent's color."""

    def test_claimed_node_gets_agent_color(self):
        nodes_data = [
            _make_node("1", ["Codebase"], "myrepo"),
            _make_node("2", ["File"], "main.py", path="main.py"),
        ]
        edges_data = [
            _make_edge("1", "2", "CONTAINS_FILE"),
        ]
        # element_id "2" is claimed by a claude agent
        claims = {"2": {"agent_name": "claude-session-1", "agent_model": "claude"}}

        ag_nodes, _ = build_agraph(nodes_data, edges_data, claims=claims)

        claimed = next(n for n in ag_nodes if n.id == "2")
        assert claimed.color == AGENT_COLORS["claude"]

    def test_unclaimed_node_keeps_type_color(self):
        nodes_data = [
            _make_node("1", ["Codebase"], "myrepo"),
            _make_node("2", ["File"], "main.py", path="main.py"),
        ]
        edges_data = []
        claims = {"2": {"agent_name": "gemini-1", "agent_model": "gemini"}}

        ag_nodes, _ = build_agraph(nodes_data, edges_data, claims=claims)

        unclaimed = next(n for n in ag_nodes if n.id == "1")
        assert unclaimed.color == NODE_COLORS["Codebase"]


class TestBuildGraphASTFilter:
    """When show_ast=False, Class and Function nodes should be excluded."""

    def test_ast_nodes_excluded(self):
        nodes_data = [
            _make_node("1", ["File"], "app.py", path="app.py"),
            _make_node("2", ["Class"], "MyClass", path="app.py"),
            _make_node("3", ["Function"], "my_func", path="app.py"),
        ]
        edges_data = [
            _make_edge("1", "2", "DEFINES_CLASS"),
            _make_edge("1", "3", "DEFINES_FUNCTION"),
        ]

        ag_nodes, ag_edges = build_agraph(
            nodes_data, edges_data, claims={}, show_ast=False
        )

        # Only the File node should survive
        assert len(ag_nodes) == 1
        assert ag_nodes[0].id == "1"
        # Edges referencing excluded nodes should also be dropped
        assert len(ag_edges) == 0

    def test_ast_nodes_included_by_default(self):
        nodes_data = [
            _make_node("1", ["File"], "app.py", path="app.py"),
            _make_node("2", ["Class"], "MyClass", path="app.py"),
        ]
        edges_data = [
            _make_edge("1", "2", "DEFINES_CLASS"),
        ]

        ag_nodes, ag_edges = build_agraph(nodes_data, edges_data, claims={})

        assert len(ag_nodes) == 2
        assert len(ag_edges) == 1
