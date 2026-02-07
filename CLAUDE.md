# broCode

Multi-agent codebase coordination system that prevents AI agents from interfering with each other when working on the same repository.

## Problem Statement

When multiple AI agents (Claude, Gemini, etc.) work on the same codebase simultaneously, they lack visibility into what each other is doing. This leads to:
- Agents modifying files another agent has in context
- Conflicting changes and broken code
- Lost work and context corruption

## Solution

A coordination layer using a Knowledge Graph (Neo4j) and Model Context Protocol (MCP) that allows agents to:
- **Claim** nodes (files/directories) they're working on
- **Query** what other agents are currently working on
- **Release** nodes when done, triggering re-indexing
- **Automatically claim** additional nodes using static analysis to lock the full impact region (including cross-repo dependencies), creating a safety net for files the agent might not know it's affecting

## Architecture

### 1. Automatic Indexer
Creates and maintains the Knowledge Graph representation of the codebase.

**Node Types:**
- `Codebase` - Root node
- `Repo` - Repository
- `Directory` - Folder
- `File` - Individual file
- `Agent` - AI agent (Claude, Gemini, etc.)
- `Function` - (Stretch goal) Function-level granularity

**Output:** Indexed repository in a format the MCP can read

### 2. MCP Server
Provides tools for agents to interact with the Knowledge Graph.

**Tools:**
- `claim_node` - Claim a file/directory the agent is working on
- `release_and_reindex` - Release claimed nodes and trigger re-indexing
- `get_active_agents` - Query which agents are working where
- `query_codebase` - Search/query the codebase structure

**Claim Reasons** (initial values, may expand):
- `direct` - Agent is actively editing this file/directory
- `in_context` - Agent has this file in memory/context
- `dependency` - File is a dependency of something being edited (auto-claimed)

### 3. Visualization (Streamlit)
Demo UI showing real-time agent activity on the codebase graph. Claimed nodes light up with agent-specific colors.

**Data Layer:**
- Uses **mock data** (`ui/data/mock_data.json`) for POC and demos
- Designed with abstraction layer (`DataProvider`) for easy Neo4j integration later
- Mock data represents the broCode repo structure with simulated claims

**Color Scheme:**
- Claude: Orange shades (direct=red-orange, in_context=orange, dependency=light orange)
- Gemini: Blue shades (direct=medium blue, in_context=royal blue, dependency=sky blue)
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
├── repo-graph/        # Indexer implementation
├── mcp/               # MCP server implementation (TODO)
└── ui/                # Streamlit visualization
    ├── app.py         # Main Streamlit entry point
    ├── config.py      # Colors, styling, settings
    ├── requirements.txt
    ├── components/    # UI components (graph, sidebar)
    └── data/          # Data layer (mock + Neo4j abstraction)
        └── mock_data.json  # Mock codebase for demos
```

## Development Guidelines

### Agent Workflow
1. When an agent brings a file into memory or plans to edit it, it should **claim** that node
2. While working, other agents querying the codebase will see the node is claimed
3. After completing work, the agent **releases** the node, triggering a re-index

### MCP Integration
The MCP server must be accessible from both Claude and Gemini. Agents should be instructed (via CLAUDE.md/system prompts) to use the claim/release tools for every file interaction.

## Agent Coding Standards (Critical)

Since multiple agents collaborate on this repo, strict adherence to these standards is required to maintain shared context.

1. **Test-Driven Development (TDD)**
   - **Write tests first**: No code is written without a failing test.
   - **Self-Documenting Tests**: Tests should clearly describe the expected behavior and edge cases, serving as executable documentation.

2. **Context-Aware Comments**
   - **Target Audience**: Write comments specifically for *other agents* who might pick up the task later.
   - **Explain "Why"**: Focus on intent, design decisions, hidden dependencies, and potential side effects.
   - **References**: explicitly link to related tickets, files, or constraints.

3. **Documentation Maintenance**
   - **Live Documentation**: If code behavior changes, `CLAUDE.md` and `CURRENT_STATE.md` MUST be updated immediately.
   - **Minimal Updates**: Keep documentation updates focused on the specific change to avoid large, conflicting diffs.
   - **State Tracking**: `CURRENT_STATE.md` is the source of truth for the project's current status. There should be one in each high-level folder.

4. **Informative Change Messages**
   - **Detail is Key**: Commit messages and pull request descriptions must be comprehensive to aid future agents.
   - **Structure**: Clearly state *what* changed, *why* it changed, and *how* it affects the system.
   - **Impact**: Explicitly mention if the change blocks or unblocks other tasks or requires specific testing.

## Demo Scenario

1. Set up a sample repo with ~5 folders (app, db, ui, etc.)
2. Claude claims 3 folders for extended work
3. UI shows these folders highlighted (orange)
4. Gemini attempts to modify something in a claimed folder
5. System returns: "Claude is currently working on this"

## Setup

### Prerequisites
- Neo4j Community Edition (local instance)
- Python 3.10+
- MCP-compatible client (Claude Code, etc.)

### Installation
```bash
# TODO: Add installation steps once implemented
```

## Commands

```bash
# UI (from repo root)
pip install -r ui/requirements.txt  # Install UI dependencies
streamlit run ui/app.py             # Start visualization UI

# TODO: Add other commands once implemented
# python -m repo_graph index .      # Re-index the codebase
# python -m mcp_server              # Start MCP server
```
