from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path

from repo_graph.models.nodes import Codebase, Directory, File

DEFAULT_IGNORE = {".git", "__pycache__", "node_modules", ".venv", "venv", ".tox"}
INDEXIGNORE_FILE = ".indexignore"


def _parse_indexignore(root: Path) -> list[str]:
    """Parse a .indexignore file and return a list of patterns."""
    ignore_path = root / INDEXIGNORE_FILE
    if not ignore_path.is_file():
        return []
    patterns = []
    for line in ignore_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line)
    return patterns


def _is_ignored(rel_path: str, patterns: list[str]) -> bool:
    """Check if a relative path matches any .indexignore pattern."""
    parts = Path(rel_path).parts
    for pattern in patterns:
        # Match against the full relative path
        if fnmatch.fnmatch(rel_path, pattern):
            return True
        # Match against any individual path component
        for part in parts:
            if fnmatch.fnmatch(part, pattern):
                return True
        # Support directory/** style patterns
        if pattern.endswith("/**"):
            prefix = pattern[:-3]
            if rel_path.startswith(prefix + "/") or rel_path == prefix:
                return True
        # Support **/name patterns (match anywhere in tree)
        if pattern.startswith("**/"):
            suffix = pattern[3:]
            if fnmatch.fnmatch(rel_path, suffix) or rel_path.endswith("/" + suffix) or any(fnmatch.fnmatch(p, suffix) for p in parts):
                return True
    return False


@dataclass
class Edge:
    """A directed relationship between two nodes."""

    source_path: str
    target_path: str
    rel_type: str  # CONTAINS_DIR | CONTAINS_FILE | DEFINES_FUNCTION | DEFINES_CLASS | HAS_METHOD | IMPORTS | CALLS
    source_label: str = ""  # extra discriminator (e.g. class name, caller function name)
    target_label: str = ""  # extra discriminator (e.g. callee function name)


@dataclass
class IndexResult:
    """The full graph produced by indexing a repository."""

    codebase: Codebase = field(default_factory=Codebase)
    directories: list[Directory] = field(default_factory=list)
    files: list[File] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)

    # AST-level nodes (populated when --analyze-python is used)
    functions: list = field(default_factory=list)
    classes: list = field(default_factory=list)


def index_repository(
    root: Path,
    ignore: set[str] | None = None,
    analyze_python: bool = False,
) -> IndexResult:
    """Walk *root* and return the file-level graph."""

    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"{root} is not a directory")

    ignore = ignore if ignore is not None else DEFAULT_IGNORE
    indexignore_patterns = _parse_indexignore(root)

    result = IndexResult(codebase=Codebase.from_path(root))

    for item in sorted(root.rglob("*")):
        # Skip anything whose path contains an ignored directory name.
        if any(part in ignore for part in item.parts):
            continue

        rel_path = str(item.relative_to(root))
        if _is_ignored(rel_path, indexignore_patterns):
            continue

        if item.is_dir():
            directory = Directory.from_path(item, root)
            result.directories.append(directory)

            parent_path = str(item.parent.relative_to(root)) if item.parent != root else ""
            source = parent_path if parent_path else root.name
            result.edges.append(Edge(
                source_path=source,
                target_path=directory.path,
                rel_type="CONTAINS_DIR",
            ))

        elif item.is_file():
            file_node = File.from_path(item, root)
            result.files.append(file_node)

            parent_path = str(item.parent.relative_to(root)) if item.parent != root else ""
            source = parent_path if parent_path else root.name
            result.edges.append(Edge(
                source_path=source,
                target_path=file_node.path,
                rel_type="CONTAINS_FILE",
            ))

    if analyze_python:
        from repo_graph.indexer.ast_analyzer import analyze_python_files

        py_files = [f for f in result.files if f.extension == ".py"]
        ast_result = analyze_python_files(py_files, root)
        result.functions = ast_result.functions
        result.classes = ast_result.classes
        result.edges.extend(ast_result.edges)

    return result
