"""Async Neo4j client for the broCode MCP server.

All Cypher execution happens here. Tools in server.py call methods on this
class — they never touch the driver directly.

Why async: FastMCP tools are async. The neo4j package supports
AsyncGraphDatabase natively, so we use it directly instead of wrapping
sync calls in run_in_executor.

This class is created once in the server lifespan and shared across all
tool invocations via ctx.lifespan_context["db"].
"""

from __future__ import annotations

import fnmatch

from neo4j import AsyncGraphDatabase

from brocode_mcp.env import Neo4jConfig
from brocode_mcp import queries

# Node types that can appear in the type_clause of QUERY_CODEBASE_TEMPLATE.
# Used as an allowlist to prevent Cypher injection via string formatting.
VALID_NODE_TYPES = {"File", "Directory", "Codebase", "Class", "Function"}


class Neo4jClient:
    """Thin async wrapper around the Neo4j async driver."""

    def __init__(self, config: Neo4jConfig) -> None:
        self._driver = AsyncGraphDatabase.driver(
            config.uri, auth=(config.username, config.password)
        )
        self._database = config.database

    async def close(self) -> None:
        await self._driver.close()

    # ------------------------------------------------------------------
    # claim_node helpers
    # ------------------------------------------------------------------

    async def check_node_exists(self, node_path: str, codebase: str) -> dict | None:
        """Return node info dict if the node exists, None otherwise."""
        async with self._driver.session(database=self._database) as session:
            return await session.execute_read(
                self._run_check_node_exists, node_path, codebase
            )

    @staticmethod
    async def _run_check_node_exists(tx, node_path: str, codebase: str) -> dict | None:
        result = await tx.run(
            queries.CHECK_NODE_EXISTS, node_path=node_path, codebase=codebase
        )
        record = await result.single()
        return dict(record) if record else None

    async def check_existing_claim(self, node_path: str, codebase: str) -> list[dict]:
        """Return list of agents that have claimed this node."""
        async with self._driver.session(database=self._database) as session:
            return await session.execute_read(
                self._run_check_existing_claim, node_path, codebase
            )

    @staticmethod
    async def _run_check_existing_claim(tx, node_path: str, codebase: str) -> list[dict]:
        result = await tx.run(
            queries.CHECK_EXISTING_CLAIM, node_path=node_path, codebase=codebase
        )
        return [dict(record) async for record in result]

    async def create_claim(
        self,
        agent_name: str,
        agent_model: str,
        node_path: str,
        codebase: str,
        claim_reason: str,
    ) -> dict | None:
        """Create Agent node (MERGE) and CLAIM relationship. Returns node info."""
        async with self._driver.session(database=self._database) as session:
            return await session.execute_write(
                self._run_create_claim,
                agent_name,
                agent_model,
                node_path,
                codebase,
                claim_reason,
            )

    @staticmethod
    async def _run_create_claim(
        tx,
        agent_name: str,
        agent_model: str,
        node_path: str,
        codebase: str,
        claim_reason: str,
    ) -> dict | None:
        result = await tx.run(
            queries.CREATE_CLAIM,
            agent_name=agent_name,
            agent_model=agent_model,
            node_path=node_path,
            codebase=codebase,
            claim_reason=claim_reason,
        )
        record = await result.single()
        return dict(record) if record else None

    # ------------------------------------------------------------------
    # release_node helpers
    # ------------------------------------------------------------------

    async def release_claim(
        self, agent_name: str, node_path: str, codebase: str
    ) -> dict | None:
        """Remove CLAIM relationship. Returns info if it existed, None otherwise."""
        async with self._driver.session(database=self._database) as session:
            return await session.execute_write(
                self._run_release_claim, agent_name, node_path, codebase
            )

    @staticmethod
    async def _run_release_claim(
        tx, agent_name: str, node_path: str, codebase: str
    ) -> dict | None:
        result = await tx.run(
            queries.RELEASE_CLAIM,
            agent_name=agent_name,
            node_path=node_path,
            codebase=codebase,
        )
        record = await result.single()
        return dict(record) if record else None

    # ------------------------------------------------------------------
    # graph update helpers (upsert / delete)
    # ------------------------------------------------------------------

    async def upsert_file(
        self,
        codebase: str,
        path: str,
        name: str,
        extension: str,
        size_bytes: int,
        parent_path: str,
    ) -> None:
        """Upsert a File node and optionally link to parent Directory."""
        async with self._driver.session(database=self._database) as session:
            await session.execute_write(
                self._run_upsert_file, codebase, path, name, extension,
                size_bytes, parent_path,
            )

    @staticmethod
    async def _run_upsert_file(
        tx, codebase: str, path: str, name: str, extension: str,
        size_bytes: int, parent_path: str,
    ) -> None:
        await tx.run(
            queries.UPSERT_FILE,
            codebase=codebase, path=path, name=name,
            extension=extension, size_bytes=size_bytes,
            parent_path=parent_path,
        )

    async def upsert_directory(
        self,
        codebase: str,
        path: str,
        name: str,
        depth: int,
        parent_path: str,
    ) -> None:
        """Upsert a Directory node and optionally link to parent Directory."""
        async with self._driver.session(database=self._database) as session:
            await session.execute_write(
                self._run_upsert_directory, codebase, path, name, depth,
                parent_path,
            )

    @staticmethod
    async def _run_upsert_directory(
        tx, codebase: str, path: str, name: str, depth: int,
        parent_path: str,
    ) -> None:
        await tx.run(
            queries.UPSERT_DIRECTORY,
            codebase=codebase, path=path, name=name,
            depth=depth, parent_path=parent_path,
        )

    async def upsert_function(
        self,
        codebase: str,
        file_path: str,
        name: str,
        line_number: int,
        is_method: bool,
        parameters: str,
        owner_class: str,
    ) -> None:
        """Upsert a Function node and link to parent File."""
        async with self._driver.session(database=self._database) as session:
            await session.execute_write(
                self._run_upsert_function, codebase, file_path, name,
                line_number, is_method, parameters, owner_class,
            )

    @staticmethod
    async def _run_upsert_function(
        tx, codebase: str, file_path: str, name: str, line_number: int,
        is_method: bool, parameters: str, owner_class: str,
    ) -> None:
        await tx.run(
            queries.UPSERT_FUNCTION,
            codebase=codebase, file_path=file_path, name=name,
            line_number=line_number, is_method=is_method,
            parameters=parameters, owner_class=owner_class,
        )

    async def upsert_class(
        self,
        codebase: str,
        file_path: str,
        name: str,
        line_number: int,
        base_classes: str,
    ) -> None:
        """Upsert a Class node and link to parent File."""
        async with self._driver.session(database=self._database) as session:
            await session.execute_write(
                self._run_upsert_class, codebase, file_path, name,
                line_number, base_classes,
            )

    @staticmethod
    async def _run_upsert_class(
        tx, codebase: str, file_path: str, name: str, line_number: int,
        base_classes: str,
    ) -> None:
        await tx.run(
            queries.UPSERT_CLASS,
            codebase=codebase, file_path=file_path, name=name,
            line_number=line_number, base_classes=base_classes,
        )

    async def delete_file(self, path: str, codebase: str) -> None:
        """Delete a File node and its AST children."""
        async with self._driver.session(database=self._database) as session:
            await session.execute_write(
                self._run_delete_file, path, codebase,
            )

    @staticmethod
    async def _run_delete_file(tx, path: str, codebase: str) -> None:
        await tx.run(queries.DELETE_FILE, path=path, codebase=codebase)

    async def delete_directory(self, path: str, codebase: str) -> None:
        """Delete a Directory node and all descendants."""
        async with self._driver.session(database=self._database) as session:
            await session.execute_write(
                self._run_delete_directory, path, codebase,
            )

    @staticmethod
    async def _run_delete_directory(tx, path: str, codebase: str) -> None:
        await tx.run(queries.DELETE_DIRECTORY, path=path, codebase=codebase)

    async def delete_function(self, file_path: str, name: str, codebase: str) -> None:
        """Delete a specific Function node."""
        async with self._driver.session(database=self._database) as session:
            await session.execute_write(
                self._run_delete_function, file_path, name, codebase,
            )

    @staticmethod
    async def _run_delete_function(
        tx, file_path: str, name: str, codebase: str
    ) -> None:
        await tx.run(
            queries.DELETE_FUNCTION,
            file_path=file_path, name=name, codebase=codebase,
        )

    async def delete_class(self, file_path: str, name: str, codebase: str) -> None:
        """Delete a Class node and its methods."""
        async with self._driver.session(database=self._database) as session:
            await session.execute_write(
                self._run_delete_class, file_path, name, codebase,
            )

    @staticmethod
    async def _run_delete_class(
        tx, file_path: str, name: str, codebase: str
    ) -> None:
        await tx.run(
            queries.DELETE_CLASS,
            file_path=file_path, name=name, codebase=codebase,
        )

    # ------------------------------------------------------------------
    # get_active_agents helpers
    # ------------------------------------------------------------------

    async def get_active_agents(self, codebase: str | None = None) -> list[dict]:
        """Return all active CLAIM relationships, optionally filtered by codebase."""
        async with self._driver.session(database=self._database) as session:
            if codebase:
                return await session.execute_read(
                    self._run_get_agents_by_codebase, codebase
                )
            return await session.execute_read(self._run_get_agents_all)

    @staticmethod
    async def _run_get_agents_all(tx) -> list[dict]:
        result = await tx.run(queries.GET_ACTIVE_AGENTS_ALL)
        return [dict(record) async for record in result]

    @staticmethod
    async def _run_get_agents_by_codebase(tx, codebase: str) -> list[dict]:
        result = await tx.run(
            queries.GET_ACTIVE_AGENTS_BY_CODEBASE, codebase=codebase
        )
        return [dict(record) async for record in result]

    # ------------------------------------------------------------------
    # query_codebase helpers
    # ------------------------------------------------------------------

    async def query_codebase(
        self,
        codebase: str,
        path_filter: str | None = None,
        node_type: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Search the graph for matching nodes with their claim status.

        node_type is validated against VALID_NODE_TYPES before being injected
        into the Cypher template. path_filter uses fnmatch-style glob applied
        in Python after retrieval (Neo4j has no built-in glob support without APOC).
        """
        if node_type and node_type not in VALID_NODE_TYPES:
            raise ValueError(
                f"Invalid node_type '{node_type}'. "
                f"Must be one of: {', '.join(sorted(VALID_NODE_TYPES))}"
            )

        type_clause = f":{node_type}" if node_type else ""

        # Build WHERE clause based on whether we're filtering by type
        if node_type == "Codebase":
            where_clause = "n.name = $codebase"
        else:
            where_clause = (
                "((n:Codebase AND n.name = $codebase) OR (n.codebase = $codebase))"
            )

        # Fetch more results if we need to filter in Python
        fetch_limit = limit * 5 if path_filter else limit

        cypher = queries.QUERY_CODEBASE_TEMPLATE.format(
            type_clause=type_clause,
            where_clause=where_clause,
        )

        async with self._driver.session(database=self._database) as session:
            records = await session.execute_read(
                self._run_query, cypher, codebase, fetch_limit
            )

        # Apply glob filter in Python for full fnmatch compatibility
        if path_filter:
            records = [
                r
                for r in records
                if fnmatch.fnmatch(r.get("node_path", ""), path_filter)
            ]

        return records[:limit]

    @staticmethod
    async def _run_query(tx, cypher: str, codebase: str, limit: int) -> list[dict]:
        result = await tx.run(cypher, codebase=codebase, limit=limit)
        return [dict(record) async for record in result]

    # ------------------------------------------------------------------
    # messaging helpers
    # ------------------------------------------------------------------

    async def check_agent_exists(self, agent_name: str) -> dict | None:
        """Return agent info dict if the Agent node exists, None otherwise."""
        async with self._driver.session(database=self._database) as session:
            return await session.execute_read(
                self._run_check_agent_exists, agent_name
            )

    @staticmethod
    async def _run_check_agent_exists(tx, agent_name: str) -> dict | None:
        result = await tx.run(
            queries.CHECK_AGENT_EXISTS, agent_name=agent_name
        )
        record = await result.single()
        return dict(record) if record else None

    async def send_message(self, to_agent: str, message_json: str) -> dict | None:
        """Append a JSON-encoded message to the target agent's messages list."""
        async with self._driver.session(database=self._database) as session:
            return await session.execute_write(
                self._run_send_message, to_agent, message_json
            )

    @staticmethod
    async def _run_send_message(tx, to_agent: str, message_json: str) -> dict | None:
        result = await tx.run(
            queries.SEND_MESSAGE, to_agent=to_agent, message=message_json
        )
        record = await result.single()
        return dict(record) if record else None

    async def get_messages(self, agent_name: str) -> list[str]:
        """Return the raw messages list (JSON strings) for an agent."""
        async with self._driver.session(database=self._database) as session:
            return await session.execute_read(
                self._run_get_messages, agent_name
            )

    @staticmethod
    async def _run_get_messages(tx, agent_name: str) -> list[str]:
        result = await tx.run(
            queries.GET_MESSAGES, agent_name=agent_name
        )
        record = await result.single()
        if record:
            return list(record["messages"])
        return []

    async def clear_messages(self, agent_name: str) -> None:
        """Clear all messages for an agent."""
        async with self._driver.session(database=self._database) as session:
            await session.execute_write(
                self._run_clear_messages, agent_name
            )

    @staticmethod
    async def _run_clear_messages(tx, agent_name: str) -> None:
        await tx.run(queries.CLEAR_MESSAGES, agent_name=agent_name)

    # ------------------------------------------------------------------
    # agent cleanup helpers
    # ------------------------------------------------------------------

    async def count_agent_claims(self, agent_name: str) -> int:
        """Return the number of remaining CLAIM relationships for an agent."""
        async with self._driver.session(database=self._database) as session:
            return await session.execute_read(
                self._run_count_agent_claims, agent_name
            )

    @staticmethod
    async def _run_count_agent_claims(tx, agent_name: str) -> int:
        result = await tx.run(
            queries.COUNT_AGENT_CLAIMS, agent_name=agent_name
        )
        record = await result.single()
        return record["claim_count"] if record else 0

    async def delete_agent(self, agent_name: str) -> None:
        """Delete an Agent node and all its relationships."""
        async with self._driver.session(database=self._database) as session:
            await session.execute_write(
                self._run_delete_agent, agent_name
            )

    @staticmethod
    async def _run_delete_agent(tx, agent_name: str) -> None:
        await tx.run(queries.DELETE_AGENT, agent_name=agent_name)
