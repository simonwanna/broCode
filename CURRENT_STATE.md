# Current State

## Status
**Phase**: Integration Complete
**Last Updated**: 2026-02-07

## Active Tasks
- [ ] Setup Basic CI/CD for TDD workflow
- [ ] Refactor: Move tests to root level (from repo-graph/, ui/, mcp_server/)

## Completed
- [x] Implement Automatic Indexer (Neo4j)
- [x] Implement MCP Server
- [x] Create Streamlit Visualization (POC with mock data)
- [x] Define claim reasons (direct, in_context, dependency)
- [x] Implement data provider abstraction layer
- [x] Connect UI to Neo4j (with toggle for mock/live data)
- [x] Add UI tests (45 tests passing)

## Key Resources
- `repo-graph/schema.example` - Node and relationship definitions
- `repo-graph/.env` - Neo4j credentials
- `ui/data/mock_data.json` - Mock codebase for UI demos
- `Skills.md` - Streamlit implementation patterns

## Component Details
- **Automatic Indexer**: Filesystem walking, Python AST analysis, .indexignore support, Neo4j persistence. 30+ tests passing. Located in `repo-graph/`.
- **MCP Server**: FastMCP server with 4 tools (`brocode_claim_node`, `brocode_release_node`, `brocode_get_active_agents`, `brocode_query_codebase`). Async Neo4j driver, stdio transport, 22 tests passing. Located in `mcp_server/`.
- **UI**: Neo4j integration complete. Toggle between mock/live data. 45 tests passing. Located in `ui/`.

## Recent Blockers
- None

## Notes for Agents
- UI has a toggle to switch between mock data and Neo4j
- Credentials are loaded from `repo-graph/.env` or environment variables
- To add new claim reasons, update both `ui/config.py` (colors) and `CLAUDE.md` (documentation)
- The MCP server uses `fastmcp>=2.0,<3` with async Neo4j driver
- Tools are accessible via `.fn` attribute when testing (FastMCP wraps in FunctionTool)
- Please update this file when:
  - A major component is completed
  - A new blocker is identified
  - The project phase changes
