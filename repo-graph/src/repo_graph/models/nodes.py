from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Codebase:
    """Root node representing an entire repository / codebase."""

    label: str = "Codebase"

    name: str = ""
    root_path: str = ""

    @staticmethod
    def from_path(path: Path) -> Codebase:
        return Codebase(name=path.name, root_path=str(path.resolve()))


@dataclass
class Directory:
    """A directory inside the codebase."""

    label: str = "Directory"

    name: str = ""
    path: str = ""
    depth: int = 0

    @staticmethod
    def from_path(path: Path, root: Path) -> Directory:
        rel = path.relative_to(root)
        return Directory(
            name=path.name,
            path=str(rel),
            depth=len(rel.parts),
        )


@dataclass
class File:
    """A single file inside the codebase."""

    label: str = "File"

    name: str = ""
    path: str = ""
    extension: str = ""
    size_bytes: int = 0

    @staticmethod
    def from_path(path: Path, root: Path) -> File:
        rel = path.relative_to(root)
        stat = path.stat()
        return File(
            name=path.name,
            path=str(rel),
            extension=path.suffix,
            size_bytes=stat.st_size,
        )
