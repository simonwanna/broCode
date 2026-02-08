# BroCode

**The Traffic Controller for AI Agents.**  
*Prevent merge conflicts and coordinate multi-agent coding sessions from different providers with a knowledge graph.*

![BroCode UI](assets/ui.png)

## What is BroCode?

When multiple AI agents (like Claude, Gemini) work on the same codebase simultaneously, they often step on each other's toes, modifying the same files, breaking dependencies, and causing merge conflicts. 

Creating software with multiple agents introduces new risks:
*   **Silent Bugs**: Agents unaware of each other's changes can introduce subtle, hard-to-trace errors.
*   **Context Collisions**: Agents overwrite work because they lack a shared understanding of "who is doing what."
*   **The "Human in the Loop" Friction**: You want to jump in with a new idea via Cursor or VS Code while agents are running, but worry about breaking their active tasks.
*   **Distributed Team Sync**: Your friend wants to work on the same repo from another computer. Instead of heavy branching and merging for every small task, BroCode coordinates your active files in real-time.

**BroCode** solves this by creating a **live Knowledge Graph** of your repository. It acts as an async coordination layer where agents and humans use the **Model Context Protocol (MCP)** to "claim" files before editing them, signalling their intent and locking down critical paths.

### Key Features

*   **🔍 Automatic Indexing**: Walks your codebase, identifying files, classes, and functions to build a Neo4j graph.
*   **🤖 MCP Server**: Native tools for agents to `claim`, `release`, and `update` nodes in the graph.
*   **📨 Message Passing**: A built-in inbox system where agents can send requests to each other (e.g., "I need this file, can you tell me when you are done with it?").
*   **🚦 Coordination**: **Exclusive Claims** lock a file for direct editing, preventing others from modifying it to avoid conflicts.
*   **👀 Real-Time UI**: A Streamlit dashboard to visualize the codebase and see exactly who is working on what.

---

## Getting Started

### Prerequisites

*   [uv](https://github.com/astral-sh/uv) (Package manager)
*   **Neo4j Database** (Local or Aura Free Tier)

### Installation

1.  **Clone the repository**
    ```bash
    git clone https://github.com/simonwanna/broCode.git
    cd broCode
    ```

2.  **Install dependencies**
    ```bash
    uv sync
    ```

3.  **Configure Environment**
    Create a `.env` file or set environment variables for your Neo4j instance:
    ```bash
    export NEO4J_URI="bolt://localhost:7687"
    export NEO4J_AUTH="neo4j/your-password"
    ```

---

## Usage

### 1. Index Your Repository
Before starting, populate the graph with your codebase structure:

```bash
uv run repo-graph . --analyze-python
```

### 2. Run the Visualization
Launch the dashboard to monitor agent activity:

```bash
uv run streamlit run ui/app.py
```

### 3. Connect Your Agents (MCP)
BroCode exposes an MCP server that agents use to coordinate.

**For Claude Code:**
```bash
claude mcp add brocode --scope project -- uv run brocode-mcp
```

**For Claude Desktop (Config):**
Add this to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "brocode": {
      "command": "uv",
      "args": ["run", "brocode-mcp"]
    }
  }
}
```
