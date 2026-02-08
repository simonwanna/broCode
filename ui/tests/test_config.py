"""
Tests for UI configuration and color logic.

Why these tests matter:
- Color selection must work correctly for visualization
- Agent colors are core to the demo
- When new agents are added, these tests catch regressions
"""

import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    AGENT_COLORS,
    UNCLAIMED_COLOR,
    UNKNOWN_AGENT_COLOR,
    NODE_STYLES,
    GRAPH_CONFIG,
    get_node_color,
    get_claim_reason_description,
)
from data.data_provider import Claim


class TestAgentColors:
    """Tests for agent color configuration."""

    def test_claude_colors_defined(self):
        """Claude must have name and base color definitions."""
        assert "agent_claude" in AGENT_COLORS

        claude = AGENT_COLORS["agent_claude"]
        assert "name" in claude
        assert "base" in claude

    def test_gemini_colors_defined(self):
        """Gemini must have name and base color definitions."""
        assert "agent_gemini" in AGENT_COLORS

        gemini = AGENT_COLORS["agent_gemini"]
        assert "name" in gemini
        assert "base" in gemini

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

    def test_claimed_node_returns_agent_base_color(self):
        """Claimed nodes should return the agent's base color regardless of claim reason."""
        claims = [Claim(agent_id="agent_claude", node_id="file_main", claim_reason="Refactoring error handling")]
        color = get_node_color("file_main", claims, AGENT_COLORS)

        expected = AGENT_COLORS["agent_claude"]["base"]
        assert color == expected

    def test_different_reasons_return_same_base_color(self):
        """Different free-text reasons for the same agent should all use the base color."""
        for reason in ["Adding tests", "Fixing bug", "Reviewing code"]:
            claims = [Claim(agent_id="agent_gemini", node_id="file_main", claim_reason=reason)]
            color = get_node_color("file_main", claims, AGENT_COLORS)
            assert color == AGENT_COLORS["agent_gemini"]["base"]

    def test_unknown_agent_returns_unknown_agent_color(self):
        """Claims from unknown agents should fall back to white (unknown agent color)."""
        claims = [Claim(agent_id="agent_unknown", node_id="file_main", claim_reason="Working on it")]
        color = get_node_color("file_main", claims, AGENT_COLORS)
        assert color == UNKNOWN_AGENT_COLOR

    def test_unrelated_claims_dont_affect_node(self):
        """Claims on other nodes should not affect this node's color."""
        claims = [Claim(agent_id="agent_claude", node_id="other_file", claim_reason="Editing")]
        color = get_node_color("file_main", claims, AGENT_COLORS)
        assert color == UNCLAIMED_COLOR

    def test_first_claim_wins_for_multiple_claims(self):
        """If multiple agents claim the same node, the first claim wins."""
        claims = [
            Claim(agent_id="agent_claude", node_id="file_main", claim_reason="Editing auth logic"),
            Claim(agent_id="agent_gemini", node_id="file_main", claim_reason="Reviewing code"),
        ]
        color = get_node_color("file_main", claims, AGENT_COLORS)
        expected = AGENT_COLORS["agent_claude"]["base"]
        assert color == expected


class TestClaimReasonDescriptions:
    """Tests for claim reason descriptions — now just passthrough."""

    def test_free_text_returns_itself(self):
        """Free-text claim reasons should be returned as-is."""
        desc = get_claim_reason_description("Adding TypeScript AST parsing support")
        assert desc == "Adding TypeScript AST parsing support"

    def test_short_text_returns_itself(self):
        """Short descriptions should also pass through."""
        desc = get_claim_reason_description("Fixing bug")
        assert desc == "Fixing bug"


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
        # Width can be int or string like "100%"
        width = GRAPH_CONFIG["width"]
        assert isinstance(width, (int, str))
        assert GRAPH_CONFIG["height"] > 0

    def test_graph_is_directed(self):
        """Graph should be directed (parent -> child)."""
        assert GRAPH_CONFIG.get("directed") is True

    def test_graph_is_hierarchical(self):
        """Graph should use hierarchical layout for directory structure."""
        assert GRAPH_CONFIG.get("hierarchical") is True
