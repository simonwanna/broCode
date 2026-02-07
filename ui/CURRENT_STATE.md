# UI - Current State

## Status
**Phase**: Schema Updated
**Last Updated**: 2026-02-07

## What Works
- Graph visualization with `streamlit-agraph`
- Color coding by agent (orange=Claude, blue=Gemini)
- Single base color per agent (exclusive/shared colors defined but not yet visualized)
- **Smart refresh** - Polls every 5 seconds but only re-renders when data changes (no blinking)
- Demo controls to simulate agent claims (free-text reasons)
- Agent status sidebar panel (only shows active agents in legend)
- **Neo4j integration** - Toggle between mock and live data
- **Real-time updates** - Claims from MCP appear automatically
- **39 tests passing**

## Architecture
```
ui/
├── app.py              # Main entry point (with Neo4j toggle)
├── config.py           # Colors, settings
├── components/
│   ├── graph.py        # Graph rendering
│   └── sidebar.py      # Agent status, demo controls
├── data/
│   ├── data_provider.py  # Mock + Neo4j providers
│   └── mock_data.json    # Mock broCode structure
└── tests/
    ├── test_data_provider.py  # DataProvider interface tests
    └── test_config.py         # Color/config tests
```

## Data Layer
- **MockDataProvider**: Reads from `mock_data.json`, stores claims in memory
- **Neo4jDataProvider**: Queries live Neo4j database, reads .env from repo-graph/
- Factory function `get_data_provider(use_mock=True/False)` to switch
- Toggle in sidebar to switch at runtime

## To Run
```bash
# From repo root
uv run streamlit run ui/app.py

# Run tests
uv run pytest ui/tests/ -v
```

## Schema Notes
- **Claim reasons** are free-text descriptions (e.g., "Refactoring error handling")
- **Claim types** (TODO): Will add `exclusive` vs `shared` visual indicators
- Agent colors are matched by name (supports "claude", "agent_claude", "claude-session-1", etc.)

## Test Coverage
- DataProvider interface contract
- Claim CRUD operations (add, remove, clear)
- Free-text claim reason handling
- Color selection by agent name
- Agent color schemes
- Graph configuration
- Neo4j provider instantiation

## Next Steps
- [ ] Add visual indicator for `exclusive` vs `shared` claims
- [ ] Add codebase selector dropdown (for multiple codebases)
- [ ] Show agent messages in sidebar
- [ ] Add conflict detection visualization

## Notes for Agents
- Toggle "Use Neo4j" in sidebar to switch data sources
- Credentials are loaded from `repo-graph/.env`
- Colors are defined in `config.py` - add new agents there
- Agent matching is fuzzy (handles session suffixes like "claude-session-1")
- Smart refresh: polls every 5s, computes data fingerprint, uses `st.stop()` if unchanged
- Legend only shows agents that are currently registered (not all defined colors)
