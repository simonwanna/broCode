"""
UI Configuration for broCode visualization.

Defines colors, styles, and settings for the graph visualization.
Colors are designed to show agent ownership and claim intensity.
"""

# Agent color schemes
# Each agent has a base color with variations for claim reasons
AGENT_COLORS = {
    "agent_claude": {
        "name": "Claude",
        "base": "#FF8C00",  # Dark orange
        "direct": "#FF4500",      # Orange-red (most intense)
        "in_context": "#FF8C00",  # Dark orange (medium)
        "dependency": "#FFB366",  # Light orange (least intense)
    },
    "agent_gemini": {
        "name": "Gemini",
        "base": "#4169E1",  # Royal blue
        "direct": "#0000CD",      # Medium blue (most intense)
        "in_context": "#4169E1",  # Royal blue (medium)
        "dependency": "#87CEEB",  # Sky blue (least intense)
    },
}

# Default color for unclaimed nodes
UNCLAIMED_COLOR = "#97C2FC"  # Light blue-gray

# Node type styling
NODE_STYLES = {
    "Directory": {
        "shape": "box",
        "size": 30,
    },
    "File": {
        "shape": "dot",
        "size": 20,
    },
    "Class": {
        "shape": "diamond",
        "size": 25,
    },
    "Function": {
        "shape": "triangle",
        "size": 15,
    },
}

# Graph layout configuration
GRAPH_CONFIG = {
    "width": 1000,
    "height": 700,
    "directed": True,
    "hierarchical": True,
    "physics": {
        "enabled": True,
        "hierarchicalRepulsion": {
            "nodeDistance": 150,
        },
    },
}

# Auto-refresh interval in milliseconds
REFRESH_INTERVAL_MS = 2000


def get_node_color(node_id: str, claims: list, agents: dict) -> str:
    """
    Determine the color for a node based on claims.

    Priority: direct > in_context > dependency
    If multiple agents claim the same node (shouldn't happen in practice),
    the first claim wins.

    Args:
        node_id: The node to color
        claims: List of Claim objects
        agents: Dict mapping agent_id to AGENT_COLORS entry

    Returns:
        Hex color string
    """
    # Find claims for this node
    node_claims = [c for c in claims if c.node_id == node_id]

    if not node_claims:
        return UNCLAIMED_COLOR

    # Priority order for claim reasons
    priority = {"direct": 0, "in_context": 1, "dependency": 2}

    # Sort by priority (direct first)
    node_claims.sort(key=lambda c: priority.get(c.claim_reason, 99))

    claim = node_claims[0]
    agent_colors = AGENT_COLORS.get(claim.agent_id, {})

    return agent_colors.get(claim.claim_reason, UNCLAIMED_COLOR)


def get_claim_reason_description(reason: str) -> str:
    """Get human-readable description of a claim reason."""
    descriptions = {
        "direct": "Actively editing",
        "in_context": "In agent's context",
        "dependency": "Dependency of claimed node",
    }
    return descriptions.get(reason, reason)
