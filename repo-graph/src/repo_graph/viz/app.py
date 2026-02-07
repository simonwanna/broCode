"""broCode — real-time codebase graph visualization.

Streamlit app that renders the Neo4j knowledge graph with live agent
claim highlights.  Nodes are colored by type; claimed nodes switch to
the claiming agent's color.

Launch via the ``brocode-viz`` entry point or ``streamlit run``.

The pure-logic helpers (primary_type, agent_color, build_agraph) are
importable without Streamlit for unit testing.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Node type → display color (Tailwind-ish hex values)
# ---------------------------------------------------------------------------

NODE_COLORS: dict[str, str] = {
    "Codebase": "#6366f1",   # indigo
    "Directory": "#3b82f6",  # blue
    "File": "#22c55e",       # green
    "Class": "#f59e0b",      # amber
    "Function": "#8b5cf6",   # violet
    "Unknown": "#6b7280",    # gray
}

# Agent model → claim highlight color
AGENT_COLORS: dict[str, str] = {
    "claude": "#f97316",     # orange
    "gemini": "#10b981",     # emerald
}

_DEFAULT_AGENT_COLOR = "#ec4899"  # pink — fallback for unknown models

# Node types considered AST-level (filterable)
_AST_TYPES = {"Class", "Function"}

# Priority order for resolving a node's canonical type from its Neo4j labels
_TYPE_PRIORITY = ["Codebase", "File", "Directory", "Class", "Function"]

# ---------------------------------------------------------------------------
# Pure helpers (tested without Streamlit)
# ---------------------------------------------------------------------------


def primary_type(labels: list[str]) -> str:
    """Resolve a list of Neo4j labels to a single canonical node type."""
    for t in _TYPE_PRIORITY:
        if t in labels:
            return t
    return "Unknown"


def agent_color(model: str) -> str:
    """Return the highlight color for an agent model."""
    return AGENT_COLORS.get(model, _DEFAULT_AGENT_COLOR)


def build_agraph(
    nodes_data: list[dict],
    edges_data: list[dict],
    claims: dict[str, dict],
    show_ast: bool = True,
) -> tuple[list, list]:
    """Convert raw Neo4j data into streamlit-agraph Node/Edge lists.

    Parameters
    ----------
    nodes_data : list[dict]
        Each dict has key ``"n"`` with sub-keys:
        ``element_id``, ``labels``, ``name``, ``path``.
    edges_data : list[dict]
        Each dict has keys ``src_id``, ``tgt_id``, ``rel_type``.
    claims : dict
        Mapping of element_id → {"agent_name", "agent_model"}.
    show_ast : bool
        If False, Class and Function nodes (and their edges) are excluded.

    Returns
    -------
    (ag_nodes, ag_edges) — lists suitable for ``streamlit_agraph.agraph()``.
    """
    # Import here so the module can be imported for testing without
    # streamlit-agraph installed.
    from streamlit_agraph import Edge, Node

    ag_nodes: list[Node] = []
    included_ids: set[str] = set()

    for row in nodes_data:
        n = row["n"]
        eid = n["element_id"]
        ntype = primary_type(n["labels"])

        # Optionally filter AST nodes
        if not show_ast and ntype in _AST_TYPES:
            continue

        # Claimed nodes get the agent's color; others get type color
        if eid in claims:
            color = agent_color(claims[eid]["agent_model"])
        else:
            color = NODE_COLORS.get(ntype, NODE_COLORS["Unknown"])

        label = n["name"] or ntype
        ag_nodes.append(
            Node(
                id=eid,
                label=label,
                color=color,
                size=30 if ntype == "Codebase" else 20 if ntype == "Directory" else 15,
                title=f"{ntype}: {n.get('path') or n['name']}",
            )
        )
        included_ids.add(eid)

    # Build edges, dropping any that reference filtered-out nodes
    ag_edges: list[Edge] = []
    for row in edges_data:
        if row["src_id"] in included_ids and row["tgt_id"] in included_ids:
            ag_edges.append(
                Edge(
                    source=row["src_id"],
                    target=row["tgt_id"],
                    label=row["rel_type"],
                    color="#475569",  # slate-600
                )
            )

    return ag_nodes, ag_edges


# ---------------------------------------------------------------------------
# Streamlit UI (only runs when executed as the app entry point)
# ---------------------------------------------------------------------------


def _run_app() -> None:
    """Streamlit page — called on every rerun."""
    import streamlit as st
    from streamlit_agraph import Config, agraph
    from streamlit_autorefresh import st_autorefresh

    from repo_graph.viz.neo4j_queries import fetch_claims, fetch_codebases, fetch_graph

    st.set_page_config(page_title="broCode Viz", layout="wide")

    # Auto-refresh every 2 seconds
    st_autorefresh(interval=2000, key="autorefresh")

    st.title("broCode — Codebase Graph")

    # ---- Sidebar ---------------------------------------------------------
    with st.sidebar:
        st.header("Settings")

        codebases = fetch_codebases()
        if not codebases:
            st.warning("No indexed codebases found in Neo4j.")
            st.stop()

        selected = st.selectbox("Codebase", codebases)
        show_ast = st.checkbox("Show AST nodes (Class / Function)", value=False)

        st.divider()

        # Fetch live data
        nodes_data, edges_data = fetch_graph(selected)
        claims = fetch_claims(selected)

        # Active agents panel
        st.header("Active Agents")
        if claims:
            agents_seen: dict[str, str] = {}
            for info in claims.values():
                agents_seen[info["agent_name"]] = info["agent_model"]
            for name, model in agents_seen.items():
                color = agent_color(model)
                st.markdown(
                    f"<span style='color:{color}; font-weight:bold'>"
                    f"● {name}</span> <small>({model})</small>",
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No active claims.")

        st.divider()

        # Color legend
        st.header("Legend")
        for ntype, color in NODE_COLORS.items():
            if not show_ast and ntype in _AST_TYPES:
                continue
            st.markdown(
                f"<span style='color:{color}'>●</span> {ntype}",
                unsafe_allow_html=True,
            )
        st.markdown("---")
        for model, color in AGENT_COLORS.items():
            st.markdown(
                f"<span style='color:{color}'>●</span> {model} (claimed)",
                unsafe_allow_html=True,
            )

    # ---- Main area -------------------------------------------------------
    ag_nodes, ag_edges = build_agraph(
        nodes_data, edges_data, claims, show_ast=show_ast
    )

    # Stats bar
    claimed_count = sum(1 for n in ag_nodes if n.id in claims)
    unique_agents = len({c["agent_name"] for c in claims.values()})
    cols = st.columns(3)
    cols[0].metric("Total Nodes", len(ag_nodes))
    cols[1].metric("Claimed", claimed_count)
    cols[2].metric("Active Agents", unique_agents)

    # Render graph
    if ag_nodes:
        config = Config(
            width="100%",
            height=700,
            directed=True,
            physics=True,
            hierarchical=False,
            nodeHighlightBehavior=True,
            highlightColor="#f97316",
            collapsible=True,
        )
        agraph(nodes=ag_nodes, edges=ag_edges, config=config)
    else:
        st.info("No nodes to display. Is the codebase indexed?")


def main() -> None:
    """CLI entry point — wraps ``streamlit run`` on this file."""
    # Load .env from repo-graph/ (same pattern as cli.py)
    _load_dotenv()
    app_path = Path(__file__).resolve()
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(app_path)],
        check=True,
    )


def _load_dotenv() -> None:
    """Load .env from cwd if it exists (zero-dep, same as cli.py)."""
    env_path = Path.cwd() / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


# When Streamlit runs this file directly, execute the app.
if __name__ == "__main__" or "streamlit" in sys.modules:
    _load_dotenv()
    _run_app()
