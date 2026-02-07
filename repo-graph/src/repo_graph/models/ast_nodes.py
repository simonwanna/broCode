from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Function:
    """A function or method definition in a Python file."""

    label: str = "Function"

    name: str = ""
    file_path: str = ""        # relative path to the containing file
    line_number: int = 0
    is_method: bool = False
    parameters: list[str] = field(default_factory=list)
    owner_class: str = ""      # class name if this is a method, empty otherwise

    @staticmethod
    def from_ast(
        name: str,
        file_path: str,
        line_number: int,
        is_method: bool,
        parameters: list[str],
        owner_class: str = "",
    ) -> Function:
        return Function(
            name=name,
            file_path=file_path,
            line_number=line_number,
            is_method=is_method,
            parameters=parameters,
            owner_class=owner_class,
        )


@dataclass
class Class:
    """A class definition in a Python file."""

    label: str = "Class"

    name: str = ""
    file_path: str = ""
    line_number: int = 0
    base_classes: list[str] = field(default_factory=list)

    @staticmethod
    def from_ast(
        name: str,
        file_path: str,
        line_number: int,
        base_classes: list[str],
    ) -> Class:
        return Class(
            name=name,
            file_path=file_path,
            line_number=line_number,
            base_classes=base_classes,
        )


