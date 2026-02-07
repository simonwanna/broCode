# Knowledge Graph Schema

This document defines the schema for the Neo4j Knowledge Graph used by the BroCode coordination system.

## 1. Node Labels

### `Codebase`
Represents the root of the repository.
- **Properties:**
  - `id`: string (UUID or "ROOT") - Unique Identifier
  - `name`: string - Name of the codebase (e.g., "broCode")
  - `root_path`: string - Absolute path to the root directory

### `Directory`
Represents a folder within the codebase.
- **Properties:**
  - `id`: string (MD5 hash of relative path) - Unique Identifier
  - `name`: string - Directory name
  - `path`: string - Relative path from root
  - `depth`: integer - Nesting level

### `File`
Represents a file within the codebase.
- **Properties:**
  - `id`: string (MD5 hash of relative path) - Unique Identifier
  - `name`: string - Filename
  - `path`: string - Relative path from root
  - `extension`: string - File extension (e.g., ".py", ".md")
  - `size_bytes`: integer - Size of the file

### `Agent`
Represents an AI agent interacting with the codebase.
- **Properties:**
  - `id`: string (UUID) - Unique Identifier for the agent instance
  - `name`: string - Agent name (e.g., "Claude-1", "Gemini-Alpha")
  - `model`: string - Underlying model (e.g., "claude-3-opus", "gemini-1.5-pro")
  - `status`: string - Current status (e.g., "IDLE", "WORKING", "WAITING")

## 2. Relationships

| Source Type | Relationship Type | Target Type | Properties | Description |
| :--- | :--- | :--- | :--- | :--- |
| `Codebase` | `CONTAINS` | `Directory` | | The codebase contains this directory. |
| `Directory` | `CONTAINS` | `Directory` | | Parent directory contains child directory. |
| `Directory` | `CONTAINS` | `File` | | Directory contains file. |
| `Agent` | `CLAIMS` | `Directory` | `timestamp`: datetime<br>`reason`: string | Agent claims exclusive access to this directory. |
| `Agent` | `CLAIMS` | `File` | `timestamp`: datetime<br>`reason`: string | Agent claims exclusive access to this file. |

## 3. ID Generation Strategy

To ensure consistency across re-indexing and agent sessions, we use deterministic IDs where possible.

- **Files & Directories**: `MD5(relative_path)`
  - *Example*: `MD5("src/main.py")` -> `a1b2...`
  - *Benefit*: Renaming a file creates a new node (correctly), but moving it might need handling. For now, path-based ID is sufficient.

- **Agents**: UUID (generated at runtime)
  - *Example*: `550e8400-e29b-41d4-a716-446655440000`
  - *Reasoning*: Agents are ephemeral instances.

## 4. Indexing & Constraints

The following constraints should be applied in Neo4j:

```cypher
CREATE CONSTRAINT FOR (n:Codebase) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT FOR (n:Directory) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT FOR (n:File) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT FOR (n:Agent) REQUIRE n.id IS UNIQUE;
```
