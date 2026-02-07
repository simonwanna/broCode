# UI - Current State

## Status
**Phase**: POC Complete + Tested
**Last Updated**: 2026-02-07

## What Works
- Graph visualization with `streamlit-agraph`
- Color coding by agent (orange=Claude, blue=Gemini)
- Color nuances by claim reason (direct, in_context, dependency)
- Auto-refresh every 2 seconds
- Demo controls to simulate agent claims
- Agent status sidebar panel
- **45 tests passing** (data provider + config)

## Architecture
```
ui/
├── app.py              # Main entry point
├── config.py           # Colors, settings
├── components/
│   ├── graph.py        # Graph rendering
│   └── sidebar.py      # Agent status, demo controls
├── data/
│   ├── data_provider.py  # Abstract data layer
│   └── mock_data.json    # Mock broCode structure
└── tests/
    ├── test_data_provider.py  # DataProvider interface tests
    └── test_config.py         # Color/config tests
```

## Data Layer
- **MockDataProvider**: Reads from `mock_data.json`, stores claims in memory
- **Neo4jDataProvider**: Stub ready for implementation
- Factory function `get_data_provider(use_mock=True)` to switch

## To Run
```bash
# From repo root
uv run streamlit run ui/app.py

# Run tests
uv run pytest ui/tests/ -v
```

## Test Coverage
- DataProvider interface contract
- Claim CRUD operations (add, remove, clear)
- Claim reason handling (direct, in_context, dependency)
- Color selection logic and priority
- Agent color schemes
- Graph configuration

## Next Steps
- [ ] Implement Neo4jDataProvider
- [ ] Add more sophisticated graph layouts
- [ ] Show claim timestamps
- [ ] Add conflict detection visualization

## Notes for Agents
- Colors are defined in `config.py` - add new agents there
- Claim reasons affect color intensity - darker = more direct
- The graph uses hierarchical layout for directory structure
- **When implementing Neo4jDataProvider, all tests in test_data_provider.py should pass**
