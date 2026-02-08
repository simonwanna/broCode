# broCode

Multi-agent codebase coordination system that prevents AI agents from interfering with each other when working on the same repository.

## Problem Statement

When multiple AI agents (Claude, Gemini, etc.) work on the same codebase simultaneously, they lack visibility into what each other is doing. This leads to:

- Agents modifying files another agent has in context
- Conflicting changes and broken code
- Lost work and context corruption

## Solution

A coordination layer using a Knowledge Graph (Neo4j) and Model Context Protocol (MCP) that allows agents to:

- **Claim** nodes with two types:
  - `exclusive` - Files being directly edited (locked from other agents)
  - `shared` - Affected files that others can edit with restrictions (no schema/interface changes)
- **Query** what other agents are currently working on
- **Release** nodes when done, triggering re-indexing
- **Message** other agents to request work on claimed files
- **Automatically claim** additional nodes using static analysis to identify the impact region (dependencies become `shared` claims)

## Architecture

### 1. Automatic Indexer

Creates and maintains the Knowledge Graph representation of the codebase.

**Node Types:**

- `Codebase` - Root node
- `Directory` - Folder
- `File` - Individual file
- `Class` - Class definition (from Python AST analysis)
- `Function` - Function/method definition (from Python AST analysis)
- `Agent` - AI agent (Claude, Gemini, etc.)

**Output:** Indexed repository in a format the MCP can read

### 2. MCP Server

Provides tools for agents to interact with the Knowledge Graph.

**Tools:**

- `brocode_claim_node` - Claim a file/directory with a description of planned work
- `brocode_release_node` - Release claimed nodes when done working
- `brocode_update_graph` - Apply per-node graph updates (upsert/delete files, dirs, functions, classes) to keep the knowledge graph in sync after editing
- `brocode_get_active_agents` - Query which agents are working where
- `brocode_query_codebase` - Search/query the codebase structure and claim status
- `brocode_send_message` - Send a message to another agent (e.g., request access to a claimed node)
- `brocode_get_messages` - Retrieve incoming messages (inbox model)
- `brocode_clear_messages` - Clear inbox after processing messages

**Claim Types:**

- `exclusive` - Files the agent is directly editing. Other agents cannot modify these.
- `shared` - Files affected by the agent's work (dependencies, imports). Other agents CAN edit these but with a warning: **do not change schemas, return types, or interfaces** that could break the exclusive claim holder's code.

**Claim Reason:**
Free-text description of what the agent plans to do. Required and cannot be empty. Examples:

- `"Refactoring error handling in login flow"`
- `"Adding unit tests for new parser"`

**Agent Messaging:**
Agents can communicate via the MCP server using an inbox model:

- If Agent A needs to modify a file that Agent B has claimed, Agent A calls `brocode_send_message` to request access. The message is stored on Agent B's Agent node.
- Agent B periodically calls `brocode_get_messages` to check for incoming requests, then `brocode_clear_messages` after processing.
- This enables coordination without blocking: Agent A continues other work while waiting.
- Messages include: sender, content, optional `node_path` for context, and a UTC timestamp.
- No self-messaging allowed (`from_agent` and `to_agent` must differ).

### 3. Visualization (Streamlit)

Demo UI showing real-time agent activity on the codebase graph. Claimed nodes light up with agent-specific colors.

**Data Layer:**

- Uses **mock data** (`ui/data/mock_data.json`) for POC and demos
- Designed with abstraction layer (`DataProvider`) for easy Neo4j integration later
- Mock data represents the broCode repo structure with simulated claims

**Color Scheme:**

- Claude: Orange (#FF8C00)
- Gemini: Blue (#4169E1)
- Unclaimed: Gray-blue

## Tech Stack

- **Database:** Neo4j Community Edition
- **Protocol:** Model Context Protocol (MCP)
- **Clients:** Claude Code, Gemini
- **UI:** Streamlit

## Skills Reference

Agents should consult `Skills.md` for implementation patterns and best practices:

- **Streamlit** - Graph visualization, real-time updates, Neo4j integration, demo controls

## Project Structure

```
broCode/
├── CLAUDE.md          # This file
├── CURRENT_STATE.md   # Current status and active tasks
├── Skills.md          # Implementation patterns for agents
├── project-skiss.md   # Original project specification
├── repo-graph/        # Automatic indexer (complete)
├── mcp_server/        # MCP server — FastMCP + async Neo4j (complete)
└── ui/                # Streamlit visualization
    ├── app.py         # Main Streamlit entry point
    ├── config.py      # Colors, styling, settings
    ├── components/    # UI components (graph, sidebar)
    ├── data/          # Data layer (mock + Neo4j abstraction)
    │   └── mock_data.json  # Mock codebase for demos
    └── tests/         # 45 tests for data provider + config
```

## Development Guidelines

### Agent Workflow

1. **Check activity** — Call `brocode_get_active_agents` to see who is working where before starting
2. **Explore** — Call `brocode_query_codebase` to find the node(s) you need
3. **Claim before editing** — Call `brocode_claim_node` for every file/directory you intend to modify. Handle `conflict` responses by using `brocode_send_message` to negotiate access
4. **Do your work** — Edit files, run tests, etc.
5. **Update the graph** — If you created, renamed, or deleted files/dirs/functions/classes, call `brocode_update_graph` to keep the knowledge graph in sync
6. **Poll messages** — Call `brocode_get_messages` periodically while holding claims, then `brocode_clear_messages` after processing
7. **Release when done** — Call `brocode_release_node` for each claimed node. The Agent node auto-deletes when its last claim is released

### MCP Integration

The MCP server must be accessible from both Claude and Gemini. Agents should be instructed (via CLAUDE.md/system prompts) to use the claim/release tools for every file interaction.

## Agent Coding Standards (Critical)

Since multiple agents collaborate on this repo, strict adherence to these standards is required to maintain shared context.

1. **Test-Driven Development (TDD)**
   - **Write tests first**: No code is written without a failing test.
   - **Self-Documenting Tests**: Tests should clearly describe the expected behavior and edge cases, serving as executable documentation.

2. **Context-Aware Comments**
   - **Target Audience**: Write comments specifically for _other agents_ who might pick up the task later.
   - **Explain "Why"**: Focus on intent, design decisions, hidden dependencies, and potential side effects.
   - **References**: explicitly link to related tickets, files, or constraints.

3. **Documentation Maintenance**
   - **Live Documentation**: If code behavior changes, `CLAUDE.md` and `CURRENT_STATE.md` MUST be updated immediately.
   - **Minimal Updates**: Keep documentation updates focused on the specific change to avoid large, conflicting diffs.
   - **State Tracking**: `CURRENT_STATE.md` is the source of truth for the project's current status. There should be one in each high-level folder.

4. **Informative Change Messages**
   - **Detail is Key**: Commit messages and pull request descriptions must be comprehensive to aid future agents.
   - **Structure**: Clearly state _what_ changed, _why_ it changed, and _how_ it affects the system.
   - **Impact**: Explicitly mention if the change blocks or unblocks other tasks or requires specific testing.

## Setup

### Prerequisites

- Neo4j (Aura cloud or local Community Edition)
- Python 3.10+
- MCP-compatible client (Claude Code, etc.)

### Installation

```bash
# 1. Install dependencies
uv sync --all-extras

# 3. Set Neo4j credentials (or create a .env file)
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USERNAME="neo4j"
export NEO4J_PASSWORD="your-password"
export NEO4J_DATABASE="neo4j"
```

### Claude Code Integration

```bash
# Add the MCP server to Claude Code
claude mcp add brocode \
  --scope project \
  -- uv run brocode-mcp
```

## Commands

```bash
# Install dependencies (from repo root)
uv sync --all-extras

# UI
uv run streamlit run ui/app.py

# Index a repository into Neo4j
uv run repo-graph /path/to/repo --analyze-python

# Run the MCP server (stdio)
uv run brocode-mcp

# Run all tests
uv run pytest ui/tests/ -v
uv run pytest repo-graph/tests/ -v
uv run pytest mcp_server/tests/ -v
```
