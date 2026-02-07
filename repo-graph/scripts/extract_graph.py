"""Extract the full graph from Neo4j and save as JSON for visualization."""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Block broken pandas in Anaconda env
sys.modules.setdefault("pandas", None)  # type: ignore[arg-type]

from neo4j import GraphDatabase  # noqa: E402


def extract(uri: str, user: str, password: str, database: str = "neo4j") -> dict:
    driver = GraphDatabase.driver(uri, auth=(user, password))

    nodes = []
    edges = []
    node_id_map: dict[str, int] = {}  # neo4j element id -> our index

    with driver.session(database=database) as session:
        # Extract all nodes
        result = session.run(
            "MATCH (n) "
            "RETURN elementId(n) AS id, labels(n)[0] AS label, properties(n) AS props "
            "ORDER BY label, props.name"
        )
        for i, record in enumerate(result):
            neo_id = record["id"]
            node_id_map[neo_id] = i
            props = dict(record["props"])
            # Convert lists to strings for JSON compatibility
            for k, v in props.items():
                if isinstance(v, list):
                    props[k] = v
            nodes.append({
                "id": i,
                "label": record["label"],
                **props,
            })

        # Extract all relationships
        result = session.run(
            "MATCH (a)-[r]->(b) "
            "RETURN elementId(a) AS source, elementId(b) AS target, type(r) AS rel_type"
        )
        for record in result:
            src = node_id_map.get(record["source"])
            tgt = node_id_map.get(record["target"])
            if src is not None and tgt is not None:
                edges.append({
                    "source": src,
                    "target": tgt,
                    "type": record["rel_type"],
                })

    driver.close()

    return {"nodes": nodes, "edges": edges}


def main() -> None:
    # Load .env from cwd
    env_path = Path.cwd() / ".env"
    env = {}
    if env_path.is_file():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()

    uri = env.get("NEO4J_URI", "bolt://localhost:7687")
    user = env.get("NEO4J_USERNAME", "neo4j")
    password = env.get("NEO4J_PASSWORD", "password")
    database = env.get("NEO4J_DATABASE", "neo4j")

    print(f"Connecting to {uri} ...")
    graph = extract(uri, user, password, database)
    print(f"  Nodes: {len(graph['nodes'])}")
    print(f"  Edges: {len(graph['edges'])}")

    out = Path(__file__).parent / "graph_data.json"
    out.write_text(json.dumps(graph, indent=2))
    print(f"Saved to {out}")


if __name__ == "__main__":
    main()
