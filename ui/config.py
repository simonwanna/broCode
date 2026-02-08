"""
UI Configuration for broCode visualization.

Defines colors, styles, and settings for the graph visualization.
Each agent has a single base color used for all their claims.
"""

# FIXME: Agent colors are hardcoded. Should be fetched from Neo4j or configurable.
# Agent color schemes — base color per agent, with exclusive/shared variations (TODO)
AGENT_COLORS = {
    "agent_claude": {
        "name": "Claude",
        "base": "#FF8C00",      # Dark orange
        "exclusive": "#FF4500", # Brighter for exclusive claims (TODO)
        "shared": "#FFB366",    # Lighter for shared claims (TODO)
    },
    "agent_gemini": {
        "name": "Gemini",
        "base": "#4169E1",      # Royal blue
        "exclusive": "#0000CD", # Darker for exclusive claims (TODO)
        "shared": "#87CEEB",    # Lighter for shared claims (TODO)
    },
    # Also support without agent_ prefix
    "claude": {
        "name": "Claude",
        "base": "#FF8C00",
        "exclusive": "#FF4500",
        "shared": "#FFB366",
    },
    "gemini": {
        "name": "Gemini",
        "base": "#4169E1",
        "exclusive": "#0000CD",
        "shared": "#87CEEB",
    },
    "antigravity": {
        "name": "Antigravity",
        "base": "#4169E1",
        "exclusive": "#0000CD",
        "shared": "#87CEEB",
    },
}

# Default color for unclaimed nodes
UNCLAIMED_COLOR = "#97C2FC"  # Light blue-gray

# Fallback color for nodes claimed by unknown agents
UNKNOWN_AGENT_COLOR = "#FFFFFF"  # White

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
    "width": 1400,
    "height": 500,
    "directed": True,
    "hierarchical": True,
    "physics": {
        "enabled": False,  # Disabled to prevent blinking on refresh
        "hierarchicalRepulsion": {
            "nodeDistance": 150,
        },
    },
}

# Auto-refresh interval in milliseconds
REFRESH_INTERVAL_MS = 15000  # 15 seconds


def _find_agent_colors(agent_id: str) -> dict:
    """
    Find agent colors by fuzzy matching agent ID.

    Handles different formats:
    - "agent_claude" (mock format)
    - "agent_claude-session-1" (Neo4j with session)
    - "claude" (simple name)
    - "Claude" (capitalized)

    FIXME: This is a workaround. Agent colors should be fetched from Neo4j
    or the matching should be based on agent properties, not string parsing.
    """
    agent_lower = agent_id.lower()

    # Direct lookup
    if agent_id in AGENT_COLORS:
        return AGENT_COLORS[agent_id]

    # Check if agent_id contains known agent names
    for key, colors in AGENT_COLORS.items():
        agent_name = colors.get("name", "").lower()
        # Match if the agent_id contains the agent name (e.g., "agent_claude-session-1" contains "claude")
        if agent_name and agent_name in agent_lower:
            return colors

    # Try with agent_ prefix removed
    clean_id = agent_lower.replace("agent_", "").split("-")[0]  # Remove prefix and session suffix
    for key, colors in AGENT_COLORS.items():
        if colors.get("name", "").lower() == clean_id:
            return colors

    return {}


def get_node_color(node_id: str, claims: list, agents: dict) -> str:
    """
    Determine the color for a node based on claims.

    If multiple agents claim the same node (shouldn't happen in practice),
    the first claim wins.

    Args:
        node_id: The node to color
        claims: List of Claim objects
        agents: Dict mapping agent_id to AGENT_COLORS entry (unused, kept for compatibility)

    Returns:
        Hex color string
    """
    # Find claims for this node
    node_claims = [c for c in claims if c.node_id == node_id]

    if not node_claims:
        return UNCLAIMED_COLOR

    claim = node_claims[0]
    agent_colors = _find_agent_colors(claim.agent_id)

    # Use white for unknown agents so claimed nodes are still visible
    return agent_colors.get("base", UNKNOWN_AGENT_COLOR)


def get_claim_reason_description(reason: str) -> str:
    """Return the claim reason description.

    Claim reasons are free-text descriptions of planned work, so the
    reason itself IS the description — just pass it through.
    """
    return reason
