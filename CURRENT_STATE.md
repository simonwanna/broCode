# Current State

## Status

**Phase**: MCP Server Complete — Full Tool Suite
**Last Updated**: 2026-02-08

## Active Tasks

- [ ] Create descriptive prompts for detailed usage of tools
- [ ] Create demo with specific use-case with a scenario (maybe on multiple computer)
- [ ] Messaging in the UI
- [ ] Implement `exclusive` vs `shared` claim types in MCP server (claim type parameter not yet in code)
- [ ] Update UI to show claim types with different visual indicators
- [ ] Fix MCP server tests when run from repo root (`uv run pytest mcp_server/tests/` fails with import error — must run from `mcp_server/` dir)

## Completed

- [x] Implement Automatic Indexer (Neo4j) — filesystem walking, Python AST analysis, .indexignore
- [x] Implement MCP Server — 8 tools, 4 resources, async Neo4j, stdio transport
- [x] Create Streamlit Visualization — graph, sidebar, demo controls
- [x] Connect UI to Neo4j (with toggle for mock/live data)
- [x] Free-text claim reasons (required `claim_reason` parameter)
- [x] Agent messaging tools (`brocode_send_message`, `brocode_get_messages`, `brocode_clear_messages`)
- [x] Graph update tool (`brocode_update_graph`) for keeping knowledge graph in sync after edits
- [x] MCP resources: agent-workflow, graph-schema, update-graph-examples, messaging protocol

## MCP Server Tools (8 tools)

| Tool                        | Purpose                                              | Status |
| --------------------------- | ---------------------------------------------------- | ------ |
| `brocode_claim_node`        | Claim a file/directory before editing                | Done   |
| `brocode_release_node`      | Release a claimed node when done                     | Done   |
| `brocode_update_graph`      | Upsert/delete File, Directory, Function, Class nodes | Done   |
| `brocode_get_active_agents` | Query who is working where                           | Done   |
| `brocode_query_codebase`    | Search codebase structure and claim status           | Done   |
| `brocode_send_message`      | Send a message to another agent                      | Done   |
| `brocode_get_messages`      | Retrieve inbox messages                              | Done   |
| `brocode_clear_messages`    | Clear inbox after processing                         | Done   |

## MCP Server Resources (4 resources)

| URI                               | Purpose                                   |
| --------------------------------- | ----------------------------------------- |
| `brocode://agent-workflow`        | Step-by-step workflow guide for agents    |
| `brocode://graph-schema`          | Node types, properties, and relationships |
| `brocode://update-graph-examples` | JSON examples for `brocode_update_graph`  |
| `brocode://messaging`             | Messaging protocol and conventions        |

## Test Coverage

- **MCP Server**: 74 tests passing (run from `mcp_server/` dir)
- **UI**: 39 tests passing

## Component Details

- **Automatic Indexer**: Filesystem walking, Python AST analysis, .indexignore support, Neo4j persistence. Located in `repo-graph/`.
- **MCP Server**: FastMCP server with 8 tools + 4 resources. Async Neo4j driver, stdio transport, lifespan-managed connection. Located in `mcp_server/`. 74 tests.
- **UI**: Streamlit visualization with Neo4j integration. Toggle between mock/live data. 39 tests. Located in `ui/`.

## Recent Blockers

- None

## Notes for Agents

- MCP server tests must be run from `mcp_server/` directory: `cd mcp_server && uv run pytest tests/ -v`
- UI tests run from repo root: `uv run pytest ui/tests/ -v`
- Credentials are loaded from `repo-graph/.env` or environment variables
- Claim reasons are free-text descriptions of planned work (required, cannot be empty)
- Agent messaging uses an inbox model: send → get → clear
- Agent nodes auto-delete when their last claim is released
- Please update this file when:
  - A major component is completed
  - A new blocker is identified
  - The project phase changes
