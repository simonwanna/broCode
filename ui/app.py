"""
broCode Visualization - Main Streamlit Application

Demo UI for visualizing multi-agent codebase coordination.
Shows which agents are claiming which nodes in real-time.

Usage:
    streamlit run ui/app.py

Why this exists:
    This UI is primarily for demos to show stakeholders how the
    multi-agent coordination system works. It visualizes the
    knowledge graph with nodes lighting up when agents claim them.
"""

import streamlit as st
from streamlit_autorefresh import st_autorefresh

import sys
from pathlib import Path

# Add ui/ to path for imports when running via streamlit
sys.path.insert(0, str(Path(__file__).parent))

from config import REFRESH_INTERVAL_MS
from data.data_provider import get_data_provider
from components.graph import render_graph
from components.sidebar import (
    render_agent_status,
    render_demo_controls,
    render_legend,
)


def main():
    # Page config
    st.set_page_config(
        page_title="broCode - Agent Coordination",
        page_icon="🤖",
        layout="wide",
    )

    # Auto-refresh for real-time updates
    st_autorefresh(interval=REFRESH_INTERVAL_MS, key="graph_refresh")

    # Initialize data provider in session state to persist claims
    if "provider" not in st.session_state:
        st.session_state.provider = get_data_provider(use_mock=True)

    provider = st.session_state.provider

    # Header
    st.title("broCode")
    st.caption("Multi-agent codebase coordination visualization")

    # Sidebar components
    render_legend()
    render_agent_status(provider)

    st.sidebar.divider()

    # Demo controls (only in demo mode)
    if render_demo_controls(provider):
        st.rerun()

    # Main content - Graph visualization
    st.subheader("Codebase Graph")

    # Stats bar
    claims = provider.get_claims()
    nodes = provider.get_nodes()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Nodes", len(nodes))
    with col2:
        st.metric("Active Claims", len(claims))
    with col3:
        active_agents = len(set(c.agent_id for c in claims))
        st.metric("Active Agents", active_agents)

    # Render the graph
    render_graph(provider)

    # Footer
    st.divider()
    st.caption(
        "This visualization updates every 2 seconds. "
        "Use the demo controls in the sidebar to simulate agent behavior."
    )


if __name__ == "__main__":
    main()
