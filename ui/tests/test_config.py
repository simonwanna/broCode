"""
Tests for UI configuration and color logic.

Why these tests matter:
- Color selection must work correctly for visualization
- Agent colors and claim reason intensity are core to the demo
- When new agents or claim reasons are added, these tests catch regressions
"""

import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    AGENT_COLORS,
    UNCLAIMED_COLOR,
    NODE_STYLES,
    GRAPH_CONFIG,
    get_node_color,
    get_claim_reason_description,
)
from data.data_provider import Claim


class TestAgentColors:
    """Tests for agent color configuration."""

    def test_claude_colors_defined(self):
        """Claude must have all required color definitions."""
        assert "agent_claude" in AGENT_COLORS

        claude = AGENT_COLORS["agent_claude"]
        assert "base" in claude
        assert "direct" in claude
        assert "in_context" in claude
        assert "dependency" in claude

    def test_gemini_colors_defined(self):
        """Gemini must have all required color definitions."""
        assert "agent_gemini" in AGENT_COLORS

        gemini = AGENT_COLORS["agent_gemini"]
        assert "base" in gemini
        assert "direct" in gemini
        assert "in_context" in gemini
        assert "dependency" in gemini

    def test_colors_are_valid_hex(self):
        """All colors must be valid hex color codes."""
        for agent_id, colors in AGENT_COLORS.items():
            for color_name, color_value in colors.items():
                if color_name == "name":
                    continue  # Skip the name field
                assert color_value.startswith("#"), f"{agent_id}.{color_name} must be hex"
                assert len(color_value) == 7, f"{agent_id}.{color_name} must be #RRGGBB format"

    def test_unclaimed_color_is_valid_hex(self):
        """Unclaimed color must be valid hex."""
        assert UNCLAIMED_COLOR.startswith("#")
        assert len(UNCLAIMED_COLOR) == 7


class TestGetNodeColor:
    """Tests for the get_node_color function."""

    def test_unclaimed_node_returns_default_color(self):
        """Nodes with no claims should return UNCLAIMED_COLOR."""
        claims = []
        color = get_node_color("some_node", claims, AGENT_COLORS)
        assert color == UNCLAIMED_COLOR

    def test_claimed_node_returns_agent_color(self):
        """Claimed nodes should return the agent's color for that claim reason."""
        claims = [Claim(agent_id="agent_claude", node_id="file_main", claim_reason="direct")]
        color = get_node_color("file_main", claims, AGENT_COLORS)

        expected = AGENT_COLORS["agent_claude"]["direct"]
        assert color == expected

    def test_in_context_claim_returns_correct_color(self):
        """in_context claims should return medium intensity color."""
        claims = [Claim(agent_id="agent_claude", node_id="file_main", claim_reason="in_context")]
        color = get_node_color("file_main", claims, AGENT_COLORS)

        expected = AGENT_COLORS["agent_claude"]["in_context"]
        assert color == expected

    def test_dependency_claim_returns_correct_color(self):
        """dependency claims should return low intensity color."""
        claims = [Claim(agent_id="agent_gemini", node_id="file_main", claim_reason="dependency")]
        color = get_node_color("file_main", claims, AGENT_COLORS)

        expected = AGENT_COLORS["agent_gemini"]["dependency"]
        assert color == expected

    def test_direct_claim_has_priority_over_in_context(self):
        """If multiple claims exist, 'direct' should take priority."""
        claims = [
            Claim(agent_id="agent_claude", node_id="file_main", claim_reason="in_context"),
            Claim(agent_id="agent_gemini", node_id="file_main", claim_reason="direct"),
        ]
        color = get_node_color("file_main", claims, AGENT_COLORS)

        # direct should win, so we expect Gemini's direct color
        expected = AGENT_COLORS["agent_gemini"]["direct"]
        assert color == expected

    def test_in_context_has_priority_over_dependency(self):
        """in_context should take priority over dependency."""
        claims = [
            Claim(agent_id="agent_gemini", node_id="file_main", claim_reason="dependency"),
            Claim(agent_id="agent_claude", node_id="file_main", claim_reason="in_context"),
        ]
        color = get_node_color("file_main", claims, AGENT_COLORS)

        # in_context should win
        expected = AGENT_COLORS["agent_claude"]["in_context"]
        assert color == expected

    def test_unknown_agent_returns_unclaimed_color(self):
        """Claims from unknown agents should fall back to unclaimed color."""
        claims = [Claim(agent_id="agent_unknown", node_id="file_main", claim_reason="direct")]
        color = get_node_color("file_main", claims, AGENT_COLORS)
        assert color == UNCLAIMED_COLOR

    def test_unrelated_claims_dont_affect_node(self):
        """Claims on other nodes should not affect this node's color."""
        claims = [Claim(agent_id="agent_claude", node_id="other_file", claim_reason="direct")]
        color = get_node_color("file_main", claims, AGENT_COLORS)
        assert color == UNCLAIMED_COLOR


class TestClaimReasonDescriptions:
    """Tests for claim reason descriptions."""

    def test_direct_description(self):
        """'direct' should have a descriptive label."""
        desc = get_claim_reason_description("direct")
        assert desc is not None
        assert len(desc) > 0
        assert "edit" in desc.lower() or "active" in desc.lower()

    def test_in_context_description(self):
        """'in_context' should have a descriptive label."""
        desc = get_claim_reason_description("in_context")
        assert desc is not None
        assert len(desc) > 0
        assert "context" in desc.lower() or "memory" in desc.lower()

    def test_dependency_description(self):
        """'dependency' should have a descriptive label."""
        desc = get_claim_reason_description("dependency")
        assert desc is not None
        assert len(desc) > 0

    def test_unknown_reason_returns_itself(self):
        """Unknown claim reasons should return the reason itself."""
        desc = get_claim_reason_description("unknown_reason")
        assert desc == "unknown_reason"


class TestNodeStyles:
    """Tests for node styling configuration."""

    def test_directory_style_defined(self):
        """Directory nodes must have styling."""
        assert "Directory" in NODE_STYLES
        assert "shape" in NODE_STYLES["Directory"]
        assert "size" in NODE_STYLES["Directory"]

    def test_file_style_defined(self):
        """File nodes must have styling."""
        assert "File" in NODE_STYLES
        assert "shape" in NODE_STYLES["File"]
        assert "size" in NODE_STYLES["File"]


class TestGraphConfig:
    """Tests for graph configuration."""

    def test_graph_dimensions_defined(self):
        """Graph must have width and height."""
        assert "width" in GRAPH_CONFIG
        assert "height" in GRAPH_CONFIG
        assert GRAPH_CONFIG["width"] > 0
        assert GRAPH_CONFIG["height"] > 0

    def test_graph_is_directed(self):
        """Graph should be directed (parent -> child)."""
        assert GRAPH_CONFIG.get("directed") is True

    def test_graph_is_hierarchical(self):
        """Graph should use hierarchical layout for directory structure."""
        assert GRAPH_CONFIG.get("hierarchical") is True
