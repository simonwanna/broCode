# Skills

Instructions and patterns for agents working on this project.

## Streamlit Development

### Setup

```bash
pip install streamlit
streamlit run ui/app.py
```

### Project-Specific Patterns

#### Graph Visualization for Agent Activity

Use `streamlit-agraph` for interactive knowledge graph display:

```python
from streamlit_agraph import agraph, Node, Edge, Config

def render_codebase_graph(nodes, edges, claimed_nodes):
    """Render the codebase graph with claimed nodes highlighted."""
    graph_nodes = []
    for node in nodes:
        color = "#FFA500" if node.id in claimed_nodes else "#97C2FC"  # Orange if claimed
        graph_nodes.append(Node(
            id=node.id,
            label=node.name,
            color=color,
            size=25
        ))

    graph_edges = [Edge(source=e.source, target=e.target) for e in edges]

    config = Config(
        width=800,
        height=600,
        directed=True,
        hierarchical=True
    )

    return agraph(nodes=graph_nodes, edges=graph_edges, config=config)
```

#### Real-Time Updates

Use `st.experimental_rerun()` or auto-refresh for live agent activity:

```python
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# Refresh every 2 seconds
st_autorefresh(interval=2000, key="graph_refresh")

# Fetch current state from Neo4j
active_agents = get_active_agents()
claimed_nodes = get_claimed_nodes()

# Render with current state
render_codebase_graph(nodes, edges, claimed_nodes)
```

#### Agent Status Panel

```python
def agent_status_panel(agents):
    """Show which agents are active and what they're working on."""
    st.sidebar.header("Active Agents")

    for agent in agents:
        with st.sidebar.expander(f"{agent.name}", expanded=True):
            st.write(f"**Status:** {agent.status}")
            st.write(f"**Claimed nodes:**")
            for node in agent.claimed_nodes:
                st.write(f"  - {node.path}")
```

#### Neo4j Connection

```python
from neo4j import GraphDatabase

@st.cache_resource
def get_neo4j_driver():
    """Cached Neo4j connection."""
    return GraphDatabase.driver(
        st.secrets["neo4j"]["uri"],
        auth=(st.secrets["neo4j"]["user"], st.secrets["neo4j"]["password"])
    )

def query_graph(cypher_query):
    """Execute a Cypher query and return results."""
    driver = get_neo4j_driver()
    with driver.session() as session:
        result = session.run(cypher_query)
        return [record.data() for record in result]
```

### File Structure for UI

```
ui/
├── app.py              # Main Streamlit entry point
├── components/
│   ├── graph.py        # Graph visualization component
│   ├── agents.py       # Agent status panel
│   └── controls.py     # Manual claim/release controls (for demo)
├── services/
│   └── neo4j_client.py # Neo4j connection and queries
└── config.py           # UI configuration
```

### Streamlit Best Practices

1. **Session State** - Use `st.session_state` for persistent data across reruns
2. **Caching** - Use `@st.cache_data` for data, `@st.cache_resource` for connections
3. **Layout** - Use `st.columns()` and `st.sidebar` for organized layouts
4. **Error Handling** - Wrap Neo4j calls in try/except with `st.error()` for user feedback

### Dependencies

```txt
streamlit>=1.28.0
streamlit-agraph>=0.0.45
streamlit-autorefresh>=1.0.1
neo4j>=5.0.0
```

### Secrets Configuration

Create `.streamlit/secrets.toml`:

```toml
[neo4j]
uri = "bolt://localhost:7687"
user = "neo4j"
password = "your_password"
```

### Demo Mode

For presentations, add manual controls to simulate agent behavior:

```python
st.sidebar.header("Demo Controls")

if st.sidebar.button("Simulate Claude claiming /app"):
    claim_node("claude", "/app")
    st.rerun()

if st.sidebar.button("Simulate Gemini checking /app"):
    result = check_node_status("/app")
    if result.claimed_by:
        st.warning(f"{result.claimed_by} is currently working on /app")
```
