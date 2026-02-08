"""
Data provider abstraction layer.

Why: Allows swapping between mock data (for POC/demos) and Neo4j (for production)
without changing the UI code. The UI only interacts with this interface.

Usage:
    provider = get_data_provider(use_mock=True)
    nodes, edges = provider.get_graph()
    claims = provider.get_claims()
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import json
import os


@dataclass
class Node:
    """Represents a node in the codebase graph."""
    id: str
    type: str  # Directory, File, Class, Function
    name: str
    path: str
    extension: Optional[str] = None
    depth: Optional[int] = None


@dataclass
class Edge:
    """Represents a relationship between nodes."""
    source: str
    target: str
    type: str  # CONTAINS_DIR, CONTAINS_FILE, DEFINES_CLASS, etc.


@dataclass
class Agent:
    """Represents an AI agent."""
    id: str
    name: str
    model: str


@dataclass
class Claim:
    """
    Represents an agent's claim on a node.

    claim_reason is a free-text description of what the agent plans to do
    with this file, e.g. "Refactoring error handling" or "Adding unit tests".

    claim_type indicates the lock level:
    - "exclusive": Agent has locked the file, others cannot edit
    - "shared": Agent is working on it but others can edit with restrictions
    """
    agent_id: str
    node_id: str
    claim_reason: str  # Free-text description of planned work
    claim_type: str = "shared"  # "exclusive" or "shared"
    timestamp: Optional[str] = None


@dataclass
class Message:
    """
    Represents a message between agents.

    Messages are stored in the agent's inbox (Agent.messages property in Neo4j).
    Used for coordination requests like "I need to edit this file you're claiming".
    """
    from_agent: str
    to_agent: str
    content: str
    message_type: str = "request"  # "request", "release", "info"
    timestamp: Optional[str] = None
    node_id: Optional[str] = None  # Related node if applicable


class DataProvider(ABC):
    """Abstract interface for data providers."""

    @abstractmethod
    def get_nodes(self) -> list[Node]:
        """Get all nodes in the codebase graph."""
        pass

    @abstractmethod
    def get_edges(self) -> list[Edge]:
        """Get all edges in the codebase graph."""
        pass

    @abstractmethod
    def get_agents(self) -> list[Agent]:
        """Get all registered agents."""
        pass

    @abstractmethod
    def get_claims(self) -> list[Claim]:
        """Get all active claims."""
        pass

    @abstractmethod
    def add_claim(self, agent_id: str, node_id: str, claim_reason: str) -> None:
        """Add a claim for an agent on a node."""
        pass

    @abstractmethod
    def remove_claim(self, agent_id: str, node_id: str) -> None:
        """Remove a claim."""
        pass

    @abstractmethod
    def clear_agent_claims(self, agent_id: str) -> None:
        """Clear all claims for an agent."""
        pass

    @abstractmethod
    def get_messages(self) -> list[Message]:
        """Get all messages from agent inboxes."""
        pass


class MockDataProvider(DataProvider):
    """
    Mock data provider for POC and demos.

    Reads initial state from mock_data.json and stores claims in memory.
    Claims can be modified at runtime for demo purposes.
    """

    def __init__(self, data_path: Optional[Path] = None):
        if data_path is None:
            data_path = Path(__file__).parent / "mock_data.json"

        with open(data_path, "r") as f:
            self._data = json.load(f)

        # Parse into dataclasses
        self._nodes = [Node(**n) for n in self._data["nodes"]]
        self._edges = [Edge(**e) for e in self._data["edges"]]
        self._agents = [Agent(**a) for a in self._data["agents"]]
        self._claims: list[Claim] = [Claim(**c) for c in self._data.get("claims", [])]

    def get_nodes(self) -> list[Node]:
        return self._nodes

    def get_edges(self) -> list[Edge]:
        return self._edges

    def get_agents(self) -> list[Agent]:
        return self._agents

    def get_claims(self) -> list[Claim]:
        return self._claims

    def add_claim(self, agent_id: str, node_id: str, claim_reason: str) -> None:
        # Remove existing claim if any
        self._claims = [c for c in self._claims
                        if not (c.agent_id == agent_id and c.node_id == node_id)]
        self._claims.append(Claim(
            agent_id=agent_id,
            node_id=node_id,
            claim_reason=claim_reason
        ))

    def remove_claim(self, agent_id: str, node_id: str) -> None:
        self._claims = [c for c in self._claims
                        if not (c.agent_id == agent_id and c.node_id == node_id)]

    def clear_agent_claims(self, agent_id: str) -> None:
        self._claims = [c for c in self._claims if c.agent_id != agent_id]

    def get_messages(self) -> list[Message]:
        """Mock provider returns messages from mock_data.json if present."""
        messages_data = self._data.get("messages", [])
        return [Message(**m) for m in messages_data]


def _load_dotenv(env_path: Path) -> None:
    """Load .env file if it exists (no third-party dependency)."""
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


class Neo4jDataProvider(DataProvider):
    """
    Neo4j data provider for production use.

    Queries the knowledge graph directly for real-time visualization.
    Reads credentials from environment variables or repo-graph/.env file.

    The UI refreshes every 2 seconds, so each method re-queries the database
    to pick up changes made by agents via the MCP server.
    """

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: str = "neo4j",
        codebase: Optional[str] = None,
    ):
        # Try to load .env from repo-graph directory
        repo_root = Path(__file__).parent.parent.parent
        env_path = repo_root / "repo-graph" / ".env"
        _load_dotenv(env_path)

        # Also try cwd/.env
        _load_dotenv(Path.cwd() / ".env")

        # Set SSL_CERT_FILE if not already set — needed for Neo4j Aura (neo4j+s://)
        # The certifi bundle ships with the venv and resolves SSL verification errors.
        if not os.environ.get("SSL_CERT_FILE"):
            try:
                import certifi
                os.environ["SSL_CERT_FILE"] = certifi.where()
            except ImportError:
                pass  # certifi not installed; SSL may still work with system certs

        # Use provided values or fall back to environment
        self._uri = uri or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        self._user = user or os.environ.get("NEO4J_USERNAME", "neo4j")
        self._password = password or os.environ.get("NEO4J_PASSWORD", "password")
        self._database = database or os.environ.get("NEO4J_DATABASE", "neo4j")
        self._codebase = codebase  # If None, queries all codebases

        # Import neo4j here to avoid import errors if not installed
        from neo4j import GraphDatabase
        self._driver = GraphDatabase.driver(self._uri, auth=(self._user, self._password))

    def close(self) -> None:
        """Close the Neo4j driver connection."""
        self._driver.close()

    def _make_node_id(self, path: str, codebase: str) -> str:
        """Create a unique node ID from path and codebase.

        Format: {codebase}_{path} - simple and unique.
        The path already includes type information implicitly.
        """
        return f"{codebase}_{path}"

    def get_nodes(self) -> list[Node]:
        """
        Get all nodes (Codebase, Directory, File) from Neo4j.

        Query fetches nodes and their properties, converting to our Node dataclass.
        """
        # Query for directories and files
        cypher = """
        MATCH (n)
        WHERE n:Directory OR n:File OR n:Codebase
        RETURN labels(n) AS labels,
               coalesce(n.path, n.name) AS path,
               n.name AS name,
               n.codebase AS codebase,
               n.depth AS depth,
               n.extension AS extension
        ORDER BY path
        """

        nodes = []
        with self._driver.session(database=self._database) as session:
            result = session.run(cypher)
            for record in result:
                labels = record["labels"]
                path = record["path"]
                name = record["name"]
                codebase = record["codebase"] or record["name"]  # Codebase nodes use name

                # Determine node type from labels
                if "Codebase" in labels:
                    node_type = "Codebase"
                elif "Directory" in labels:
                    node_type = "Directory"
                elif "File" in labels:
                    node_type = "File"
                else:
                    continue

                # Filter by codebase if specified
                if self._codebase and codebase != self._codebase:
                    continue

                node_id = self._make_node_id(path, codebase)
                nodes.append(Node(
                    id=node_id,
                    type=node_type,
                    name=name,
                    path=path,
                    extension=record.get("extension"),
                    depth=record.get("depth"),
                ))

        return nodes

    def get_edges(self) -> list[Edge]:
        """
        Get all edges (CONTAINS_DIR, CONTAINS_FILE) from Neo4j.

        Query fetches relationships between nodes.
        """
        cypher = """
        MATCH (parent)-[r:CONTAINS_DIR|CONTAINS_FILE]->(child)
        RETURN labels(parent) AS parent_labels,
               coalesce(parent.path, parent.name) AS parent_path,
               parent.codebase AS parent_codebase,
               parent.name AS parent_name,
               type(r) AS rel_type,
               labels(child) AS child_labels,
               coalesce(child.path, child.name) AS child_path,
               child.codebase AS child_codebase
        """

        edges = []
        with self._driver.session(database=self._database) as session:
            result = session.run(cypher)
            for record in result:
                parent_labels = record["parent_labels"]
                child_labels = record["child_labels"]

                # Determine types
                if "Codebase" in parent_labels:
                    parent_type = "Codebase"
                    parent_codebase = record["parent_name"]
                else:
                    parent_type = "Directory" if "Directory" in parent_labels else "File"
                    parent_codebase = record["parent_codebase"]

                if "Directory" in child_labels:
                    child_type = "Directory"
                else:
                    child_type = "File"

                child_codebase = record["child_codebase"]

                # Filter by codebase if specified
                if self._codebase and parent_codebase != self._codebase:
                    continue

                source_id = self._make_node_id(record["parent_path"], parent_codebase)
                target_id = self._make_node_id(record["child_path"], child_codebase)

                edges.append(Edge(
                    source=source_id,
                    target=target_id,
                    type=record["rel_type"],
                ))

        return edges

    def get_agents(self) -> list[Agent]:
        """
        Get all registered agents from Neo4j.

        Query fetches Agent nodes.
        """
        cypher = """
        MATCH (a:Agent)
        RETURN a.name AS name, a.model AS model
        """

        agents = []
        with self._driver.session(database=self._database) as session:
            result = session.run(cypher)
            for record in result:
                name = record["name"]
                model = record["model"] or "unknown"
                agent_id = f"agent_{name.lower().replace(' ', '_')}"
                agents.append(Agent(
                    id=agent_id,
                    name=name,
                    model=model,
                ))

        return agents

    def get_claims(self) -> list[Claim]:
        """
        Get all active claims from Neo4j.

        Query fetches CLAIM relationships between Agents and nodes.
        """
        cypher = """
        MATCH (a:Agent)-[c:CLAIM]->(n)
        RETURN a.name AS agent_name,
               labels(n) AS node_labels,
               coalesce(n.path, n.name) AS node_path,
               coalesce(n.codebase, n.name) AS codebase,
               c.claim_reason AS claim_reason
        """

        claims = []
        with self._driver.session(database=self._database) as session:
            result = session.run(cypher)
            for record in result:
                agent_name = record["agent_name"]
                node_labels = record["node_labels"]
                node_path = record["node_path"]
                codebase = record["codebase"]
                claim_reason = record["claim_reason"] or "direct"

                # Filter by codebase if specified
                if self._codebase and codebase != self._codebase:
                    continue

                # Determine node type
                if "Codebase" in node_labels:
                    node_type = "Codebase"
                elif "Directory" in node_labels:
                    node_type = "Directory"
                elif "File" in node_labels:
                    node_type = "File"
                else:
                    continue

                agent_id = f"agent_{agent_name.lower().replace(' ', '_')}"
                node_id = self._make_node_id(node_path, codebase)

                claims.append(Claim(
                    agent_id=agent_id,
                    node_id=node_id,
                    claim_reason=claim_reason,
                ))

        return claims

    def add_claim(self, agent_id: str, node_id: str, claim_reason: str) -> None:
        """
        Add a claim in Neo4j.

        Note: In production, claims should be made through the MCP server.
        This is primarily for demo purposes in the UI.
        """
        # Extract agent name from agent_id (e.g., "agent_claude" -> "Claude")
        agent_name = agent_id.replace("agent_", "").replace("_", " ").title()

        # We need to find the node by ID - parse it back
        # node_id format: "type_codebase_path"
        parts = node_id.split("_", 2)
        if len(parts) < 3:
            return

        node_type = parts[0].title()
        # The rest is codebase_path, but we need to handle this carefully
        # For now, query to find the node

        cypher = """
        MERGE (a:Agent {name: $agent_name})
        WITH a
        MATCH (n)
        WHERE (n:Codebase OR n:Directory OR n:File)
          AND coalesce(n.path, n.name) CONTAINS $path_hint
        WITH a, n LIMIT 1
        MERGE (a)-[c:CLAIM]->(n)
        SET c.claim_reason = $claim_reason
        """

        # Extract a path hint from the node_id
        path_hint = parts[2].replace("_", "/") if len(parts) > 2 else ""

        with self._driver.session(database=self._database) as session:
            session.run(cypher, agent_name=agent_name, path_hint=path_hint, claim_reason=claim_reason)

    def remove_claim(self, agent_id: str, node_id: str) -> None:
        """
        Remove a claim in Neo4j.

        Note: In production, claims should be released through the MCP server.
        """
        agent_name = agent_id.replace("agent_", "").replace("_", " ").title()
        parts = node_id.split("_", 2)
        path_hint = parts[2].replace("_", "/") if len(parts) > 2 else ""

        cypher = """
        MATCH (a:Agent {name: $agent_name})-[c:CLAIM]->(n)
        WHERE coalesce(n.path, n.name) CONTAINS $path_hint
        DELETE c
        """

        with self._driver.session(database=self._database) as session:
            session.run(cypher, agent_name=agent_name, path_hint=path_hint)

    def clear_agent_claims(self, agent_id: str) -> None:
        """
        Clear all claims for an agent in Neo4j.
        """
        agent_name = agent_id.replace("agent_", "").replace("_", " ").title()

        cypher = """
        MATCH (a:Agent {name: $agent_name})-[c:CLAIM]->()
        DELETE c
        """

        with self._driver.session(database=self._database) as session:
            session.run(cypher, agent_name=agent_name)

    def get_messages(self) -> list[Message]:
        """
        Get all messages from agent inboxes in Neo4j.

        Messages are stored as JSON strings in the Agent.messages property.
        """
        cypher = """
        MATCH (a:Agent)
        WHERE a.messages IS NOT NULL AND size(a.messages) > 0
        RETURN a.name AS agent_name, a.messages AS messages
        """

        all_messages = []
        with self._driver.session(database=self._database) as session:
            result = session.run(cypher)
            for record in result:
                agent_name = record["agent_name"]
                messages_json = record["messages"] or []

                for msg_str in messages_json:
                    try:
                        msg_data = json.loads(msg_str) if isinstance(msg_str, str) else msg_str
                        all_messages.append(Message(
                            from_agent=msg_data.get("from", "unknown"),
                            to_agent=agent_name,
                            content=msg_data.get("content", ""),
                            message_type=msg_data.get("type", "info"),
                            timestamp=msg_data.get("timestamp"),
                            node_id=msg_data.get("node_id"),
                        ))
                    except (json.JSONDecodeError, TypeError):
                        continue

        return all_messages


def get_data_provider(use_mock: bool = True, **kwargs) -> DataProvider:
    """
    Factory function to get the appropriate data provider.

    Args:
        use_mock: If True, use mock data. If False, connect to Neo4j.
        **kwargs: Additional arguments for the provider:
            - For mock: data_path (Path to mock JSON file)
            - For Neo4j: uri, user, password, database, codebase

    Returns:
        DataProvider instance
    """
    if use_mock:
        return MockDataProvider(kwargs.get("data_path"))
    else:
        return Neo4jDataProvider(
            uri=kwargs.get("uri"),
            user=kwargs.get("user"),
            password=kwargs.get("password"),
            database=kwargs.get("database", "neo4j"),
            codebase=kwargs.get("codebase"),
        )
