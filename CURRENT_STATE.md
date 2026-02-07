# Current State

## Status
**Phase**: Schema Evolution
**Last Updated**: 2026-02-07

## Active Tasks
- [ ] Implement `exclusive` vs `shared` claim types in MCP server
- [ ] Add agent messaging tools (`send_message`, `get_messages`)
- [ ] Update UI to show claim types with different visual indicators
- [ ] Setup Basic CI/CD for TDD workflow

## Completed
- [x] Implement Automatic Indexer (Neo4j)
- [x] Implement MCP Server (basic claim/release)
- [x] Create Streamlit Visualization
- [x] Connect UI to Neo4j (with toggle for mock/live data)
- [x] Update to free-text claim reasons (39 tests passing)

## Schema Changes (Recent)
- **Claim reasons** are now free-text descriptions (e.g., "Refactoring error handling")
- **Claim types** (TODO): `exclusive` (locked) vs `shared` (editable with restrictions)
- **Agent messaging** (TODO): Agents can request work from other agents on claimed files

## Key Resources
- `repo-graph/schema.example` - Node and relationship definitions
- `repo-graph/.env` - Neo4j credentials
- `ui/data/mock_data.json` - Mock codebase for UI demos
- `Skills.md` - Streamlit implementation patterns

## Component Details
- **Automatic Indexer**: Filesystem walking, Python AST analysis, .indexignore support, Neo4j persistence. Located in `repo-graph/`.
- **MCP Server**: FastMCP server with claim/release/query tools. Async Neo4j driver, stdio transport. Located in `mcp_server/`.
- **UI**: Neo4j integration complete. Toggle between mock/live data. 39 tests passing. Located in `ui/`.

## Recent Blockers
- None

## Notes for Agents
- UI has a toggle to switch between mock data and Neo4j
- Credentials are loaded from `repo-graph/.env` or environment variables
- Claim reasons are free-text descriptions of planned work
- Agent colors are based on agent name (Claude=orange, Gemini=blue)
- Please update this file when:
  - A major component is completed
  - A new blocker is identified
  - The project phase changes
