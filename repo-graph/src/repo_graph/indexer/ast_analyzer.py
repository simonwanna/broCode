from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from repo_graph.models.nodes import File
from repo_graph.models.ast_nodes import Function, Class
from repo_graph.indexer.filesystem import Edge


@dataclass
class AstAnalysisResult:
    """Results from AST analysis of Python files."""

    functions: list[Function] = field(default_factory=list)
    classes: list[Class] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)


# ---------------------------------------------------------------------------
# AST Visitor
# ---------------------------------------------------------------------------

class _AstVisitor(ast.NodeVisitor):
    """Walk a single Python file's AST and extract functions, classes,
    and call-site information."""

    def __init__(self, rel_path: str) -> None:
        self.rel_path = rel_path

        self.functions: list[Function] = []
        self.classes: list[Class] = []

        # Context stacks for tracking nesting
        self._class_stack: list[str] = []
        self._function_stack: list[str] = []  # qualified names

        # Raw calls: (caller_qualified_name, callee_raw_name, lineno)
        self.calls: list[Tuple[str, str, int]] = []

    # -- Classes -----------------------------------------------------------

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        base_names: list[str] = []
        for base in node.bases:
            try:
                base_names.append(ast.unparse(base))
            except Exception:
                base_names.append("<unknown>")

        self.classes.append(Class.from_ast(
            name=node.name,
            file_path=self.rel_path,
            line_number=node.lineno,
            base_classes=base_names,
        ))

        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    # -- Functions / methods -----------------------------------------------

    def _visit_function(self, node: ast.FunctionDef) -> None:
        is_method = len(self._class_stack) > 0
        owner_class = self._class_stack[-1] if is_method else ""

        params: list[str] = []
        for arg in node.args.args:
            params.append(arg.arg)
        for arg in node.args.posonlyargs:
            params.append(arg.arg)
        for arg in node.args.kwonlyargs:
            params.append(arg.arg)
        if node.args.vararg:
            params.append(node.args.vararg.arg)
        if node.args.kwarg:
            params.append(node.args.kwarg.arg)

        self.functions.append(Function.from_ast(
            name=node.name,
            file_path=self.rel_path,
            line_number=node.lineno,
            is_method=is_method,
            parameters=params,
            owner_class=owner_class,
        ))

        qualified = f"{owner_class}.{node.name}" if is_method else node.name
        self._function_stack.append(qualified)
        self.generic_visit(node)
        self._function_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # type: ignore[arg-type]
        self._visit_function(node)  # type: ignore[arg-type]

    # -- Calls -------------------------------------------------------------

    def visit_Call(self, node: ast.Call) -> None:
        if self._function_stack:
            caller = self._function_stack[-1]
            callee = _resolve_call_name(node)
            if callee:
                self.calls.append((caller, callee, node.lineno))
        self.generic_visit(node)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_call_name(node: ast.Call) -> Optional[str]:
    """Best-effort extraction of the callee name from an ast.Call node."""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _parse_single_file(abs_path: Path, rel_path: str) -> Optional[_AstVisitor]:
    """Parse a single Python file and return a populated visitor, or None on failure."""
    try:
        source = abs_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(abs_path))
    except SyntaxError:
        return None

    visitor = _AstVisitor(rel_path)
    visitor.visit(tree)
    return visitor


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_python_files(
    files: list[File],
    root: Path,
) -> AstAnalysisResult:
    """Parse all given Python files and return AST-level nodes and edges."""

    result = AstAnalysisResult()

    # Per-file data keyed by relative path
    visitors: Dict[str, _AstVisitor] = {}

    # Phase 1: Parse each file
    for f in files:
        abs_path = root / f.path
        visitor = _parse_single_file(abs_path, f.path)
        if visitor is None:
            continue
        visitors[f.path] = visitor
        result.functions.extend(visitor.functions)
        result.classes.extend(visitor.classes)

    # Phase 2: Build DEFINES_FUNCTION and DEFINES_CLASS edges
    for rel_path, visitor in visitors.items():
        for func in visitor.functions:
            if not func.is_method:
                result.edges.append(Edge(
                    source_path=rel_path,
                    target_path=func.name,
                    rel_type="DEFINES_FUNCTION",
                ))

        for cls in visitor.classes:
            result.edges.append(Edge(
                source_path=rel_path,
                target_path=cls.name,
                rel_type="DEFINES_CLASS",
            ))

    # Phase 3: Build HAS_METHOD edges
    for rel_path, visitor in visitors.items():
        for func in visitor.functions:
            if func.is_method and func.owner_class:
                result.edges.append(Edge(
                    source_path=rel_path,
                    target_path=func.name,
                    rel_type="HAS_METHOD",
                    source_label=func.owner_class,
                ))

    # Phase 4: Build CALLS edges (function → function, best-effort)
    #
    # Build a global lookup: function name → list of (file_path, func_name)
    # so we can resolve cross-file calls.  When a name is ambiguous (defined
    # in multiple files), we prefer a same-file match; otherwise we take the
    # first cross-file match.
    global_funcs: Dict[str, List[Tuple[str, str]]] = {}
    for fpath, visitor in visitors.items():
        for fn in visitor.functions:
            global_funcs.setdefault(fn.name, []).append((fpath, fn.name))

    for rel_path, visitor in visitors.items():
        local_funcs = {fn.name for fn in visitor.functions}

        for caller_qualified, callee_name, _lineno in visitor.calls:
            caller_name = caller_qualified

            callee_file: Optional[str] = None
            callee_func_name = callee_name

            # Same file first (highest confidence)
            if callee_name in local_funcs:
                callee_file = rel_path
            # Cross-file: look up in the global index
            elif callee_name in global_funcs:
                candidates = global_funcs[callee_name]
                # Pick the first match (there may be duplicates across files)
                callee_file, callee_func_name = candidates[0]

            if callee_file:
                result.edges.append(Edge(
                    source_path=rel_path,
                    target_path=callee_file,
                    rel_type="CALLS",
                    source_label=caller_name,
                    target_label=callee_func_name,
                ))

    return result
