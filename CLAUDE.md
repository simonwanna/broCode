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
- **Analyze** the impact of modifications using static analysis to identify affected regions, even across other repositories

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

### 3. Visualization (Streamlit)
Demo UI showing real-time agent activity on the codebase graph. Claimed nodes light up with agent-specific colors.

## Tech Stack

- **Database:** Neo4j Community Edition
- **Protocol:** Model Context Protocol (MCP)
- **Clients:** Claude Code, Gemini
- **UI:** Streamlit

## Project Structure

```
broCode/
├── CLAUDE.md          # This file
├── project-skiss.md   # Original project specification
├── indexer/           # Automatic indexer (TODO)
├── mcp/               # MCP server implementation (TODO)
└── ui/                # Streamlit visualization (TODO)
```

## Development Guidelines

### Agent Workflow
1. When an agent brings a file into memory or plans to edit it, it should **claim** that node
2. While working, other agents querying the codebase will see the node is claimed
3. After completing work, the agent **releases** the node, triggering a re-index

### MCP Integration
The MCP server must be accessible from both Claude and Gemini. Agents should be instructed (via CLAUDE.md/system prompts) to use the claim/release tools for every file interaction.

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
# TODO: Add common commands once implemented
# npm run index     # Re-index the codebase
# npm run mcp       # Start MCP server
# npm run ui        # Start Streamlit visualization
```
