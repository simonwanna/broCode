"""
Sidebar components for agent status and demo controls.

Shows active agents, their claims, and provides demo controls
to simulate agent behavior during presentations.
"""

import streamlit as st

from config import AGENT_COLORS, get_claim_reason_description
from data.data_provider import DataProvider


def render_agent_status(provider: DataProvider) -> None:
    """
    Render the agent status panel showing active claims.

    Args:
        provider: Data provider instance
    """
    st.sidebar.header("Active Agents")

    agents = provider.get_agents()
    claims = provider.get_claims()
    nodes = {n.id: n for n in provider.get_nodes()}

    for agent in agents:
        agent_claims = [c for c in claims if c.agent_id == agent.id]
        agent_colors = AGENT_COLORS.get(agent.id, {})
        base_color = agent_colors.get("base", "#888888")

        # Agent header with color indicator
        st.sidebar.markdown(
            f"<div style='border-left: 4px solid {base_color}; padding-left: 8px;'>"
            f"<strong>{agent.name}</strong> ({agent.model})</div>",
            unsafe_allow_html=True
        )

        if agent_claims:
            for claim in agent_claims:
                node = nodes.get(claim.node_id)
                if node:
                    reason_desc = get_claim_reason_description(claim.claim_reason)
                    claim_color = agent_colors.get(claim.claim_reason, base_color)
                    st.sidebar.markdown(
                        f"<span style='color: {claim_color};'>●</span> "
                        f"{node.name} <small>({reason_desc})</small>",
                        unsafe_allow_html=True
                    )
        else:
            st.sidebar.caption("No active claims")

        st.sidebar.divider()


def render_demo_controls(provider: DataProvider) -> bool:
    """
    Render demo controls for simulating agent behavior.

    Args:
        provider: Data provider instance

    Returns:
        True if state was modified (triggers rerun)
    """
    st.sidebar.header("Demo Controls")

    agents = provider.get_agents()
    nodes = provider.get_nodes()

    # Select agent
    agent_names = [a.name for a in agents]
    selected_agent_name = st.sidebar.selectbox("Agent", agent_names)
    selected_agent = next(a for a in agents if a.name == selected_agent_name)

    # Select node (filter to directories and files for simplicity)
    node_options = [(n.id, f"{n.name} ({n.type})") for n in nodes]
    selected_node_id = st.sidebar.selectbox(
        "Node",
        options=[n[0] for n in node_options],
        format_func=lambda x: next(n[1] for n in node_options if n[0] == x)
    )

    # Select claim reason
    claim_reason = st.sidebar.selectbox(
        "Claim Reason",
        ["direct", "in_context", "dependency"]
    )

    # Action buttons
    col1, col2 = st.sidebar.columns(2)

    modified = False

    with col1:
        if st.button("Claim", use_container_width=True):
            provider.add_claim(selected_agent.id, selected_node_id, claim_reason)
            modified = True

    with col2:
        if st.button("Release", use_container_width=True):
            provider.remove_claim(selected_agent.id, selected_node_id)
            modified = True

    # Clear all claims for agent
    if st.sidebar.button(f"Clear all {selected_agent_name} claims", use_container_width=True):
        provider.clear_agent_claims(selected_agent.id)
        modified = True

    return modified


def render_legend() -> None:
    """Render the color legend for claim reasons."""
    st.sidebar.header("Legend")

    st.sidebar.markdown("**Claim Intensity:**")
    st.sidebar.markdown(
        """
        - 🔴 **Direct** - Actively editing
        - 🟠 **In Context** - In agent's memory
        - 🟡 **Dependency** - Related file
        """
    )

    st.sidebar.markdown("**Agent Colors:**")
    for agent_id, colors in AGENT_COLORS.items():
        st.sidebar.markdown(
            f"<span style='color: {colors['base']};'>●</span> {colors['name']}",
            unsafe_allow_html=True
        )
