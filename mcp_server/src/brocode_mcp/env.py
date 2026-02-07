"""Load Neo4j connection configuration from environment variables.

Replicates the .env loading pattern from repo_graph/cli.py (lines 12-24)
without importing from that package, keeping the two packages decoupled.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Neo4jConfig:
    """Immutable Neo4j connection parameters."""

    uri: str
    username: str
    password: str
    database: str


def _load_dotenv() -> None:
    """Load .env file from cwd if it exists (no third-party dependency)."""
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


def load_neo4j_config() -> Neo4jConfig:
    """Read Neo4j connection details from environment variables.

    Looks for NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE.
    Falls back to sensible defaults for local development.
    """
    _load_dotenv()
    return Neo4jConfig(
        uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        username=os.environ.get("NEO4J_USERNAME", "neo4j"),
        password=os.environ.get("NEO4J_PASSWORD", "password"),
        database=os.environ.get("NEO4J_DATABASE", "neo4j"),
    )
