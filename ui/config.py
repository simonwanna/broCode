"""
UI Configuration for broCode visualization.

Defines colors, styles, and settings for the graph visualization.
Each agent has a single base color used for all their claims.
"""

# Agent color schemes — one base color per agent
AGENT_COLORS = {
    "agent_claude": {
        "name": "Claude",
        "base": "#FF8C00",  # Dark orange
    },
    "agent_gemini": {
        "name": "Gemini",
        "base": "#4169E1",  # Royal blue
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

    claim = node_claims[0]
    agent_colors = AGENT_COLORS.get(claim.agent_id, {})

    return agent_colors.get("base", UNCLAIMED_COLOR)


def get_claim_reason_description(reason: str) -> str:
    """Return the claim reason description.

    Claim reasons are free-text descriptions of planned work, so the
    reason itself IS the description — just pass it through.
    """
    return reason
