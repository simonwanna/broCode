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
    """
    agent_id: str
    node_id: str
    claim_reason: str  # Free-text description of planned work
    timestamp: Optional[str] = None


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


class Neo4jDataProvider(DataProvider):
    """
    Neo4j data provider for production use.

    TODO: Implement when connecting to real Neo4j instance.
    Will query the knowledge graph directly.
    """

    def __init__(self, uri: str, user: str, password: str):
        # TODO: Initialize Neo4j driver
        raise NotImplementedError("Neo4j provider not yet implemented")

    def get_nodes(self) -> list[Node]:
        raise NotImplementedError()

    def get_edges(self) -> list[Edge]:
        raise NotImplementedError()

    def get_agents(self) -> list[Agent]:
        raise NotImplementedError()

    def get_claims(self) -> list[Claim]:
        raise NotImplementedError()

    def add_claim(self, agent_id: str, node_id: str, claim_reason: str) -> None:
        raise NotImplementedError()

    def remove_claim(self, agent_id: str, node_id: str) -> None:
        raise NotImplementedError()

    def clear_agent_claims(self, agent_id: str) -> None:
        raise NotImplementedError()


def get_data_provider(use_mock: bool = True, **kwargs) -> DataProvider:
    """
    Factory function to get the appropriate data provider.

    Args:
        use_mock: If True, use mock data. If False, connect to Neo4j.
        **kwargs: Additional arguments for the provider (e.g., Neo4j credentials)

    Returns:
        DataProvider instance
    """
    if use_mock:
        return MockDataProvider(kwargs.get("data_path"))
    else:
        return Neo4jDataProvider(
            uri=kwargs["uri"],
            user=kwargs["user"],
            password=kwargs["password"]
        )
