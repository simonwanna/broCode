# UI - Current State

## Status
**Phase**: Neo4j Integration Complete
**Last Updated**: 2026-02-07

## What Works
- Graph visualization with `streamlit-agraph`
- Color coding by agent (orange=Claude, blue=Gemini)
- Color nuances by claim reason (direct, in_context, dependency)
- Auto-refresh every 2 seconds
- Demo controls to simulate agent claims
- Agent status sidebar panel
- **Neo4j integration** - Toggle between mock and live data
- **Real-time updates** - Claims from MCP appear automatically
- **45 tests passing**

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

## Neo4j Integration
- Reads credentials from `repo-graph/.env` or environment variables
- Queries: Codebase, Directory, File nodes + CLAIM relationships
- Refreshes every 2 seconds to pick up MCP changes
- Falls back to mock data if connection fails

## Test Coverage
- DataProvider interface contract
- Claim CRUD operations (add, remove, clear)
- Claim reason handling (direct, in_context, dependency)
- Color selection logic and priority
- Agent color schemes
- Graph configuration
- Neo4j provider instantiation

## Next Steps
- [ ] Add codebase selector dropdown (for multiple codebases)
- [ ] Add more sophisticated graph layouts
- [ ] Show claim timestamps
- [ ] Add conflict detection visualization

## Notes for Agents
- Toggle "Use Neo4j" in sidebar to switch data sources
- Credentials are loaded from `repo-graph/.env`
- Colors are defined in `config.py` - add new agents there
- Claim reasons affect color intensity - darker = more direct


## Claim reasons
- direct - Agent is actively editing this file/directory
- in_context - Agent has this file in memory/context
- dependency - File is a dependency of something being edited (auto-claimed)