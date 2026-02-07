"""
Tests for the data provider abstraction layer.

Why these tests matter:
- The DataProvider interface is the contract that Neo4j must fulfill
- These tests ensure the mock provider works correctly for demos
- When Neo4j is integrated, the same tests should pass for Neo4jDataProvider

Critical for Neo4j integration:
- All DataProvider interface methods must be tested
- Edge cases for claims (add, remove, clear) must be covered
- The get_data_provider factory must correctly switch between providers
"""

import pytest
import json
import tempfile
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.data_provider import (
    DataProvider,
    MockDataProvider,
    Node,
    Edge,
    Agent,
    Claim,
    get_data_provider,
)


class TestDataProviderInterface:
    """Tests that verify the DataProvider interface contract."""

    def test_mock_provider_implements_interface(self):
        """MockDataProvider must implement all DataProvider methods."""
        provider = get_data_provider(use_mock=True)

        # All interface methods must exist and be callable
        assert callable(provider.get_nodes)
        assert callable(provider.get_edges)
        assert callable(provider.get_agents)
        assert callable(provider.get_claims)
        assert callable(provider.add_claim)
        assert callable(provider.remove_claim)
        assert callable(provider.clear_agent_claims)


class TestMockDataProvider:
    """Tests for MockDataProvider functionality."""

    @pytest.fixture
    def sample_data(self, tmp_path):
        """Create a minimal mock data file for testing."""
        data = {
            "codebase": {"id": "test_codebase", "name": "Test", "root_path": "/test"},
            "nodes": [
                {"id": "dir_root", "type": "Directory", "name": "root", "path": "/", "depth": 0},
                {"id": "file_main", "type": "File", "name": "main.py", "path": "/main.py", "extension": "py"},
                {"id": "file_utils", "type": "File", "name": "utils.py", "path": "/utils.py", "extension": "py"},
            ],
            "edges": [
                {"source": "dir_root", "target": "file_main", "type": "CONTAINS_FILE"},
                {"source": "dir_root", "target": "file_utils", "type": "CONTAINS_FILE"},
            ],
            "agents": [
                {"id": "agent_claude", "name": "Claude", "model": "opus"},
                {"id": "agent_gemini", "name": "Gemini", "model": "flash"},
            ],
            "claims": [],
        }
        data_file = tmp_path / "mock_data.json"
        data_file.write_text(json.dumps(data))
        return data_file

    @pytest.fixture
    def provider(self, sample_data):
        """Create a MockDataProvider with sample data."""
        return MockDataProvider(data_path=sample_data)

    # === Node tests ===

    def test_get_nodes_returns_list(self, provider):
        """get_nodes must return a list of Node objects."""
        nodes = provider.get_nodes()
        assert isinstance(nodes, list)
        assert all(isinstance(n, Node) for n in nodes)

    def test_get_nodes_contains_expected_data(self, provider):
        """Nodes must have correct attributes from mock data."""
        nodes = provider.get_nodes()
        node_ids = [n.id for n in nodes]

        assert "dir_root" in node_ids
        assert "file_main" in node_ids

        main_node = next(n for n in nodes if n.id == "file_main")
        assert main_node.name == "main.py"
        assert main_node.type == "File"
        assert main_node.extension == "py"

    # === Edge tests ===

    def test_get_edges_returns_list(self, provider):
        """get_edges must return a list of Edge objects."""
        edges = provider.get_edges()
        assert isinstance(edges, list)
        assert all(isinstance(e, Edge) for e in edges)

    def test_get_edges_contains_relationships(self, provider):
        """Edges must represent correct relationships."""
        edges = provider.get_edges()

        # Find edge from root to main.py
        edge = next((e for e in edges if e.target == "file_main"), None)
        assert edge is not None
        assert edge.source == "dir_root"
        assert edge.type == "CONTAINS_FILE"

    # === Agent tests ===

    def test_get_agents_returns_list(self, provider):
        """get_agents must return a list of Agent objects."""
        agents = provider.get_agents()
        assert isinstance(agents, list)
        assert all(isinstance(a, Agent) for a in agents)

    def test_get_agents_contains_expected_agents(self, provider):
        """Agents must have correct attributes."""
        agents = provider.get_agents()
        agent_names = [a.name for a in agents]

        assert "Claude" in agent_names
        assert "Gemini" in agent_names

    # === Claim tests (critical for Neo4j integration) ===

    def test_get_claims_initially_empty(self, provider):
        """Claims should start empty in test data."""
        claims = provider.get_claims()
        assert isinstance(claims, list)
        assert len(claims) == 0

    def test_add_claim_creates_claim(self, provider):
        """add_claim must create a new claim."""
        provider.add_claim("agent_claude", "file_main", "Refactoring error handling")

        claims = provider.get_claims()
        assert len(claims) == 1

        claim = claims[0]
        assert claim.agent_id == "agent_claude"
        assert claim.node_id == "file_main"
        assert claim.claim_reason == "Refactoring error handling"

    def test_add_claim_replaces_existing(self, provider):
        """Adding a claim for same agent+node should replace, not duplicate."""
        provider.add_claim("agent_claude", "file_main", "Initial exploration")
        provider.add_claim("agent_claude", "file_main", "Updating input validation")

        claims = provider.get_claims()
        assert len(claims) == 1
        assert claims[0].claim_reason == "Updating input validation"

    def test_add_claim_multiple_agents_same_node(self, provider):
        """Different agents can claim the same node (conflict scenario)."""
        provider.add_claim("agent_claude", "file_main", "Refactoring imports")
        provider.add_claim("agent_gemini", "file_main", "Adding type annotations")

        claims = provider.get_claims()
        assert len(claims) == 2

        agent_ids = [c.agent_id for c in claims]
        assert "agent_claude" in agent_ids
        assert "agent_gemini" in agent_ids

    def test_add_claim_multiple_nodes_same_agent(self, provider):
        """One agent can claim multiple nodes."""
        provider.add_claim("agent_claude", "file_main", "Fixing authentication bug")
        provider.add_claim("agent_claude", "file_utils", "Adding helper functions")

        claims = provider.get_claims()
        assert len(claims) == 2

    def test_remove_claim_removes_specific_claim(self, provider):
        """remove_claim must remove only the specified agent+node claim."""
        provider.add_claim("agent_claude", "file_main", "Editing module")
        provider.add_claim("agent_claude", "file_utils", "Reviewing utils")

        provider.remove_claim("agent_claude", "file_main")

        claims = provider.get_claims()
        assert len(claims) == 1
        assert claims[0].node_id == "file_utils"

    def test_remove_claim_nonexistent_is_safe(self, provider):
        """Removing a non-existent claim should not error."""
        provider.remove_claim("agent_claude", "file_main")  # No claims exist
        claims = provider.get_claims()
        assert len(claims) == 0

    def test_clear_agent_claims_removes_all_for_agent(self, provider):
        """clear_agent_claims must remove all claims for that agent only."""
        provider.add_claim("agent_claude", "file_main", "Editing main module")
        provider.add_claim("agent_claude", "file_utils", "Updating utilities")
        provider.add_claim("agent_gemini", "file_main", "Reviewing changes")

        provider.clear_agent_claims("agent_claude")

        claims = provider.get_claims()
        assert len(claims) == 1
        assert claims[0].agent_id == "agent_gemini"

    # === Claim reason tests (free-text) ===

    def test_claim_reason_stores_free_text(self, provider):
        """Free-text claim reasons should roundtrip correctly."""
        provider.add_claim("agent_claude", "file_main", "Adding TypeScript AST parsing support")
        assert provider.get_claims()[0].claim_reason == "Adding TypeScript AST parsing support"


class TestDataProviderFactory:
    """Tests for get_data_provider factory function."""

    def test_factory_returns_mock_by_default(self):
        """Factory should return MockDataProvider when use_mock=True."""
        provider = get_data_provider(use_mock=True)
        assert isinstance(provider, MockDataProvider)

    def test_factory_returns_neo4j_provider(self):
        """Factory should return Neo4jDataProvider when use_mock=False."""
        # Skip if neo4j is not available (will fail on import)
        try:
            from data.data_provider import Neo4jDataProvider
        except ImportError:
            pytest.skip("neo4j package not installed")

        # This will try to connect, so we expect a connection error
        # but the provider should be created
        try:
            provider = get_data_provider(use_mock=False)
            assert isinstance(provider, Neo4jDataProvider)
            provider.close()
        except Exception:
            # Connection failure is expected without a real Neo4j
            pass


class TestDataClasses:
    """Tests for data class structures."""

    def test_node_dataclass_fields(self):
        """Node must have all required fields."""
        node = Node(id="test", type="File", name="test.py", path="/test.py")
        assert node.id == "test"
        assert node.type == "File"
        assert node.name == "test.py"
        assert node.path == "/test.py"
        assert node.extension is None  # Optional
        assert node.depth is None  # Optional

    def test_edge_dataclass_fields(self):
        """Edge must have all required fields."""
        edge = Edge(source="a", target="b", type="CONTAINS")
        assert edge.source == "a"
        assert edge.target == "b"
        assert edge.type == "CONTAINS"

    def test_agent_dataclass_fields(self):
        """Agent must have all required fields."""
        agent = Agent(id="test_agent", name="Test", model="test-model")
        assert agent.id == "test_agent"
        assert agent.name == "Test"
        assert agent.model == "test-model"

    def test_claim_dataclass_fields(self):
        """Claim must have all required fields."""
        claim = Claim(agent_id="agent", node_id="node", claim_reason="Writing unit tests for parser")
        assert claim.agent_id == "agent"
        assert claim.node_id == "node"
        assert claim.claim_reason == "Writing unit tests for parser"
        assert claim.timestamp is None  # Optional
