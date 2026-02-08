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
from data.data_provider import get_data_provider, Neo4jDataProvider
from components.graph import render_graph
from components.sidebar import (
    render_agent_status,
    render_legend,
)


def main():
    # Page config
    st.set_page_config(
        page_title="broCode - Agent Coordination",
        page_icon="🤖",
        layout="wide",
    )

    # Make graph fill full width
    st.markdown("""
        <style>
        .stMainBlockContainer { max-width: 100%; padding-left: 1rem; padding-right: 1rem; }
        iframe { width: 100% !important; }
        </style>
    """, unsafe_allow_html=True)

    # Auto-refresh for real-time updates
    st.sidebar.caption(f"Refresh interval: 8000ms")
    st_autorefresh(interval=8000, key="refresh_8s")

    # Data source toggle in sidebar
    st.sidebar.header("Data Source")

    # Check if we need to switch providers
    use_neo4j = st.sidebar.toggle("Use Neo4j", value=st.session_state.get("use_neo4j", False))

    # Track if the toggle changed
    if "use_neo4j" not in st.session_state:
        st.session_state.use_neo4j = use_neo4j
    elif st.session_state.use_neo4j != use_neo4j:
        st.session_state.use_neo4j = use_neo4j
        # Clear the provider to force re-creation
        if "provider" in st.session_state:
            del st.session_state.provider

    # Initialize or get data provider
    if "provider" not in st.session_state:
        if use_neo4j:
            try:
                st.session_state.provider = get_data_provider(use_mock=False)
                st.sidebar.success("Connected to Neo4j")
            except Exception as e:
                st.sidebar.error(f"Neo4j connection failed: {e}")
                st.session_state.provider = get_data_provider(use_mock=True)
                st.session_state.use_neo4j = False
        else:
            st.session_state.provider = get_data_provider(use_mock=True)

    provider = st.session_state.provider

    # Show connection status
    if use_neo4j and isinstance(provider, Neo4jDataProvider):
        st.sidebar.caption("🟢 Live data from Neo4j")
    else:
        st.sidebar.caption("🟡 Using mock data")

    st.sidebar.divider()

    # Header
    st.title("broCode")
    st.caption("Multi-agent codebase coordination visualization")

    # Sidebar components
    render_legend(provider)
    render_agent_status(provider)

    # Main content - Graph visualization
    st.subheader("Codebase Graph")

    # Stats bar
    try:
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

        # Messages section
        st.subheader("Agent Messages")
        messages = provider.get_messages()

        if messages:
            for msg in messages:
                # Color-code by message type
                if msg.message_type == "request":
                    icon = "📨"
                elif msg.message_type == "release":
                    icon = "✅"
                else:
                    icon = "💬"

                node_info = f" (re: `{msg.node_id}`)" if msg.node_id else ""
                timestamp = f" [{msg.timestamp}]" if msg.timestamp else ""

                st.markdown(
                    f"{icon} **{msg.from_agent}** → **{msg.to_agent}**{node_info}{timestamp}  \n"
                    f"_{msg.content}_"
                )
        else:
            st.caption("No messages")

    except Exception as e:
        st.error(f"Error loading data: {e}")
        st.info("Try switching to mock data or check Neo4j connection.")

    # Debug section
    with st.expander("Debug Info"):
        node_ids = {n.id for n in nodes}
        st.write(f"**Total nodes:** {len(nodes)}, **Total claims:** {len(claims)}")

        st.write("**Claims with match status:**")
        for c in claims[:5]:
            match = "✅" if c.node_id in node_ids else "❌"
            st.code(f"{match} agent={c.agent_id}, node={c.node_id}")

        st.write("**Sample Node IDs (first 5):**")
        for n in nodes[:5]:
            st.code(f"{n.id}")

    # Footer
    st.divider()
    if use_neo4j:
        st.caption(
            "Live updates from Neo4j. Claims made via MCP will appear automatically."
        )
    else:
        st.caption(
            "Using mock data. Toggle 'Use Neo4j' for live data."
        )


if __name__ == "__main__":
    main()
