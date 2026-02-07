"""
UI Configuration for broCode visualization.

Defines colors, styles, and settings for the graph visualization.
Colors are designed to show agent ownership and claim intensity.
"""

# FIXME: Agent colors are currently hardcoded. In the future, these should be
# fetched dynamically from Neo4j or configured via UI. Any agent name containing
# "claude" should use orange, "gemini" should use blue, etc.
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
    # Also support without agent_ prefix
    "claude": {
        "name": "Claude",
        "base": "#FF8C00",
        "direct": "#FF4500",
        "in_context": "#FF8C00",
        "dependency": "#FFB366",
    },
    "gemini": {
        "name": "Gemini",
        "base": "#4169E1",
        "direct": "#0000CD",
        "in_context": "#4169E1",
        "dependency": "#87CEEB",
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

    Priority: direct > in_context > dependency
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

    # Priority order for claim reasons
    priority = {"direct": 0, "in_context": 1, "dependency": 2}

    # Sort by priority (direct first)
    node_claims.sort(key=lambda c: priority.get(c.claim_reason, 99))

    claim = node_claims[0]
    agent_colors = _find_agent_colors(claim.agent_id)

    if not agent_colors:
        return UNCLAIMED_COLOR

    # Try to get color for specific claim_reason, fall back to base color
    color = agent_colors.get(claim.claim_reason)
    if not color:
        color = agent_colors.get("base", UNCLAIMED_COLOR)
    return color


def get_claim_reason_description(reason: str) -> str:
    """Get human-readable description of a claim reason."""
    descriptions = {
        "direct": "Actively editing",
        "in_context": "In agent's context",
        "dependency": "Dependency of claimed node",
    }
    return descriptions.get(reason, reason)
