"""
Graph visualization component using streamlit-agraph.

Renders the codebase as an interactive graph with nodes colored
based on agent claims.
"""

from streamlit_agraph import agraph, Node, Edge, Config

from config import (
    AGENT_COLORS,
    NODE_STYLES,
    GRAPH_CONFIG,
    UNCLAIMED_COLOR,
    get_node_color,
)
from data.data_provider import DataProvider, Claim


def render_graph(provider: DataProvider) -> None:
    """
    Render the codebase graph with claim highlighting.

    Args:
        provider: Data provider instance
    """
    nodes = provider.get_nodes()
    edges = provider.get_edges()
    claims = provider.get_claims()

    # Build graph nodes with appropriate colors
    graph_nodes = []
    for node in nodes:
        style = NODE_STYLES.get(node.type, {"shape": "dot", "size": 20})
        color = get_node_color(node.id, claims, AGENT_COLORS)

        # Create label with icon based on type
        if node.type == "Directory":
            label = f"📁 {node.name}"
        elif node.type == "File":
            label = f"📄 {node.name}"
        else:
            label = node.name

        graph_nodes.append(Node(
            id=node.id,
            label=label,
            color=color,
            size=style["size"],
            shape=style["shape"],
            title=f"{node.path}\nType: {node.type}",  # Tooltip
        ))

    # Build graph edges
    graph_edges = [
        Edge(
            source=e.source,
            target=e.target,
            color="#888888",
        )
        for e in edges
    ]

    # Configure the graph
    config = Config(
        width=GRAPH_CONFIG["width"],
        height=GRAPH_CONFIG["height"],
        directed=GRAPH_CONFIG["directed"],
        hierarchical=GRAPH_CONFIG["hierarchical"],
        physics=GRAPH_CONFIG["physics"]["enabled"],
        nodeHighlightBehavior=True,
        highlightColor="#F7A7A6",
        collapsible=False,
    )

    # Render
    agraph(nodes=graph_nodes, edges=graph_edges, config=config)


def get_claimed_nodes_summary(provider: DataProvider) -> dict:
    """
    Get a summary of claimed nodes grouped by agent.

    Returns:
        Dict mapping agent_name -> list of (node_name, claim_reason)
    """
    claims = provider.get_claims()
    agents = {a.id: a for a in provider.get_agents()}
    nodes = {n.id: n for n in provider.get_nodes()}

    summary = {}
    for claim in claims:
        agent = agents.get(claim.agent_id)
        node = nodes.get(claim.node_id)

        if agent and node:
            agent_name = agent.name
            if agent_name not in summary:
                summary[agent_name] = []
            summary[agent_name].append({
                "node": node.name,
                "path": node.path,
                "reason": claim.claim_reason,
            })

    return summary
