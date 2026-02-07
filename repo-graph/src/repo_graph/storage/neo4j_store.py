from __future__ import annotations

from neo4j import GraphDatabase

from repo_graph.indexer.filesystem import IndexResult


class Neo4jStore:
    """Persist an IndexResult into Neo4j."""

    def __init__(self, uri: str, user: str, password: str, database: str = "neo4j") -> None:
        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        self._database = database

    def close(self) -> None:
        self._driver.close()

    def __enter__(self) -> Neo4jStore:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def save(self, result: IndexResult) -> None:
        """Write the full index result as a single transaction."""
        with self._driver.session(database=self._database) as session:
            session.execute_write(self._create_graph, result)

    def clear(self, codebase_name: str) -> None:
        """Remove all nodes belonging to a codebase."""
        cypher = (
            "MATCH (c:Codebase {name: $name}) "
            "OPTIONAL MATCH (c)-[*]->(n) "
            "DETACH DELETE c, n"
        )
        with self._driver.session(database=self._database) as session:
            session.run(cypher, name=codebase_name)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _create_graph(tx, result: IndexResult) -> None:
        cb = result.codebase

        # Codebase node
        tx.run(
            "MERGE (c:Codebase {name: $name}) "
            "SET c.root_path = $root_path",
            name=cb.name,
            root_path=cb.root_path,
        )

        # Directory nodes
        for d in result.directories:
            tx.run(
                "MERGE (d:Directory {path: $path, codebase: $codebase}) "
                "SET d.name = $name, d.depth = $depth",
                path=d.path,
                codebase=cb.name,
                name=d.name,
                depth=d.depth,
            )

        # File nodes
        for f in result.files:
            tx.run(
                "MERGE (f:File {path: $path, codebase: $codebase}) "
                "SET f.name = $name, f.extension = $extension, "
                "    f.size_bytes = $size_bytes",
                path=f.path,
                codebase=cb.name,
                name=f.name,
                extension=f.extension,
                size_bytes=f.size_bytes,
            )

        # Function nodes
        for func in result.functions:
            tx.run(
                "MERGE (fn:Function {file_path: $file_path, name: $name, "
                "       line_number: $line_number, codebase: $codebase}) "
                "SET fn.is_method = $is_method, fn.parameters = $params, "
                "    fn.owner_class = $owner_class",
                file_path=func.file_path,
                name=func.name,
                line_number=func.line_number,
                codebase=cb.name,
                is_method=func.is_method,
                params=func.parameters,
                owner_class=func.owner_class,
            )

        # Class nodes
        for cls in result.classes:
            tx.run(
                "MERGE (cl:Class {file_path: $file_path, name: $name, codebase: $codebase}) "
                "SET cl.line_number = $line_number, cl.base_classes = $base_classes",
                file_path=cls.file_path,
                name=cls.name,
                codebase=cb.name,
                line_number=cls.line_number,
                base_classes=cls.base_classes,
            )

        # Edges
        for edge in result.edges:
            rel = edge.rel_type

            # -- File-system edges -----------------------------------------
            if rel in ("CONTAINS_DIR", "CONTAINS_FILE"):
                if edge.source_path == cb.name:
                    if rel == "CONTAINS_DIR":
                        tx.run(
                            "MATCH (c:Codebase {name: $codebase}) "
                            "MATCH (d:Directory {path: $target, codebase: $codebase}) "
                            "MERGE (c)-[:CONTAINS_DIR]->(d)",
                            codebase=cb.name,
                            target=edge.target_path,
                        )
                    else:
                        tx.run(
                            "MATCH (c:Codebase {name: $codebase}) "
                            "MATCH (f:File {path: $target, codebase: $codebase}) "
                            "MERGE (c)-[:CONTAINS_FILE]->(f)",
                            codebase=cb.name,
                            target=edge.target_path,
                        )
                else:
                    if rel == "CONTAINS_DIR":
                        tx.run(
                            "MATCH (parent:Directory {path: $source, codebase: $codebase}) "
                            "MATCH (child:Directory {path: $target, codebase: $codebase}) "
                            "MERGE (parent)-[:CONTAINS_DIR]->(child)",
                            codebase=cb.name,
                            source=edge.source_path,
                            target=edge.target_path,
                        )
                    else:
                        tx.run(
                            "MATCH (d:Directory {path: $source, codebase: $codebase}) "
                            "MATCH (f:File {path: $target, codebase: $codebase}) "
                            "MERGE (d)-[:CONTAINS_FILE]->(f)",
                            codebase=cb.name,
                            source=edge.source_path,
                            target=edge.target_path,
                        )

            # -- AST edges -------------------------------------------------
            elif rel == "DEFINES_FUNCTION":
                tx.run(
                    "MATCH (f:File {path: $source, codebase: $codebase}) "
                    "MATCH (fn:Function {file_path: $source, name: $target, codebase: $codebase}) "
                    "WHERE fn.is_method = false "
                    "MERGE (f)-[:DEFINES_FUNCTION]->(fn)",
                    codebase=cb.name,
                    source=edge.source_path,
                    target=edge.target_path,
                )

            elif rel == "DEFINES_CLASS":
                tx.run(
                    "MATCH (f:File {path: $source, codebase: $codebase}) "
                    "MATCH (cl:Class {file_path: $source, name: $target, codebase: $codebase}) "
                    "MERGE (f)-[:DEFINES_CLASS]->(cl)",
                    codebase=cb.name,
                    source=edge.source_path,
                    target=edge.target_path,
                )

            elif rel == "HAS_METHOD":
                tx.run(
                    "MATCH (cl:Class {file_path: $file_path, name: $class_name, codebase: $codebase}) "
                    "MATCH (fn:Function {file_path: $file_path, name: $method_name, codebase: $codebase, "
                    "       owner_class: $class_name}) "
                    "MERGE (cl)-[:HAS_METHOD]->(fn)",
                    codebase=cb.name,
                    file_path=edge.source_path,
                    class_name=edge.source_label,
                    method_name=edge.target_path,
                )

            elif rel == "CALLS":
                tx.run(
                    "MATCH (caller:Function {file_path: $caller_file, name: $caller_name, codebase: $codebase}) "
                    "MATCH (callee:Function {file_path: $callee_file, name: $callee_name, codebase: $codebase}) "
                    "MERGE (caller)-[:CALLS]->(callee)",
                    codebase=cb.name,
                    caller_file=edge.source_path,
                    caller_name=edge.source_label,
                    callee_file=edge.target_path,
                    callee_name=edge.target_label,
                )
