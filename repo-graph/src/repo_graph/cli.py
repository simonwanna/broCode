from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from repo_graph.indexer.filesystem import index_repository
from repo_graph.storage.neo4j_store import Neo4jStore


def _load_dotenv() -> None:
    """Load .env file from cwd if it exists (no extra dependency)."""
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


def main(argv: list[str] | None = None) -> None:
    _load_dotenv()

    parser = argparse.ArgumentParser(
        prog="repo-graph",
        description="Index a repository into a Neo4j graph database.",
    )
    parser.add_argument("path", type=Path, help="Root path of the repository to index")
    parser.add_argument("--neo4j-uri", default=os.environ.get("NEO4J_URI", "bolt://localhost:7687"), help="Neo4j bolt URI")
    parser.add_argument("--neo4j-user", default=os.environ.get("NEO4J_USERNAME", "neo4j"), help="Neo4j username")
    parser.add_argument("--neo4j-password", default=os.environ.get("NEO4J_PASSWORD", "password"), help="Neo4j password")
    parser.add_argument("--neo4j-database", default=os.environ.get("NEO4J_DATABASE", "neo4j"), help="Neo4j database name")
    parser.add_argument("--analyze-python", action="store_true", help="Parse Python files to extract functions, classes, imports, and call relationships")
    parser.add_argument("--clear", action="store_true", help="Remove existing data for this codebase before indexing")
    parser.add_argument("--dry-run", action="store_true", help="Index and print stats without writing to Neo4j")

    args = parser.parse_args(argv)

    root = args.path.resolve()
    if not root.is_dir():
        print(f"Error: {root} is not a directory", file=sys.stderr)
        sys.exit(1)

    print(f"Indexing {root} ...")
    result = index_repository(root, analyze_python=args.analyze_python)

    print(f"  Directories: {len(result.directories)}")
    print(f"  Files:       {len(result.files)}")
    if args.analyze_python:
        print(f"  Functions:   {len(result.functions)}")
        print(f"  Classes:     {len(result.classes)}")
    print(f"  Edges:       {len(result.edges)}")

    if args.dry_run:
        print("Dry run — skipping Neo4j write.")
        return

    with Neo4jStore(args.neo4j_uri, args.neo4j_user, args.neo4j_password, args.neo4j_database) as store:
        if args.clear:
            print(f"Clearing existing data for codebase '{result.codebase.name}' ...")
            store.clear(result.codebase.name)

        store.save(result)
        print("Done — graph written to Neo4j.")
