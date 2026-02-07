from pathlib import Path

from repo_graph.indexer.ast_analyzer import analyze_python_files, AstAnalysisResult
from repo_graph.indexer.filesystem import index_repository
from repo_graph.models.nodes import File


def _make_file(tmp_path: Path, rel: str, content: str) -> File:
    """Helper: write a file and return a File node for it."""
    abs_path = tmp_path / rel
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_text(content)
    return File(name=abs_path.name, path=rel, extension=abs_path.suffix, size_bytes=len(content))


# -- Function extraction ---------------------------------------------------


def test_extract_top_level_functions(tmp_path: Path) -> None:
    f = _make_file(tmp_path, "app.py", "def hello():\n    pass\n\ndef world(x, y):\n    pass\n")

    result = analyze_python_files([f], tmp_path)

    names = [fn.name for fn in result.functions]
    assert "hello" in names
    assert "world" in names
    assert len(result.functions) == 2

    world_fn = [fn for fn in result.functions if fn.name == "world"][0]
    assert world_fn.is_method is False
    assert "x" in world_fn.parameters
    assert "y" in world_fn.parameters


def test_extract_async_function(tmp_path: Path) -> None:
    f = _make_file(tmp_path, "server.py", "async def handler(request):\n    pass\n")

    result = analyze_python_files([f], tmp_path)

    assert len(result.functions) == 1
    assert result.functions[0].name == "handler"
    assert "request" in result.functions[0].parameters


def test_parameters_extraction(tmp_path: Path) -> None:
    f = _make_file(tmp_path, "utils.py", "def foo(a, b, c=10, *args, **kwargs):\n    pass\n")

    result = analyze_python_files([f], tmp_path)

    params = result.functions[0].parameters
    assert "a" in params
    assert "b" in params
    assert "c" in params
    assert "args" in params
    assert "kwargs" in params


# -- Class extraction ------------------------------------------------------


def test_extract_class_with_methods(tmp_path: Path) -> None:
    code = (
        "class Dog:\n"
        "    def __init__(self, name):\n"
        "        self.name = name\n"
        "\n"
        "    def bark(self):\n"
        "        pass\n"
        "\n"
        "def standalone():\n"
        "    pass\n"
    )
    f = _make_file(tmp_path, "animals.py", code)

    result = analyze_python_files([f], tmp_path)

    assert len(result.classes) == 1
    assert result.classes[0].name == "Dog"

    methods = [fn for fn in result.functions if fn.is_method]
    non_methods = [fn for fn in result.functions if not fn.is_method]
    assert len(methods) == 2  # __init__, bark
    assert len(non_methods) == 1  # standalone

    method_names = {m.name for m in methods}
    assert method_names == {"__init__", "bark"}

    for m in methods:
        assert m.owner_class == "Dog"


def test_extract_base_classes(tmp_path: Path) -> None:
    code = "class MyList(list, object):\n    pass\n"
    f = _make_file(tmp_path, "custom.py", code)

    result = analyze_python_files([f], tmp_path)

    assert result.classes[0].base_classes == ["list", "object"]


# -- Edge building ---------------------------------------------------------


def test_defines_function_edges(tmp_path: Path) -> None:
    f = _make_file(tmp_path, "app.py", "def hello():\n    pass\n")

    result = analyze_python_files([f], tmp_path)

    def_edges = [e for e in result.edges if e.rel_type == "DEFINES_FUNCTION"]
    assert len(def_edges) == 1
    assert def_edges[0].source_path == "app.py"
    assert def_edges[0].target_path == "hello"


def test_defines_class_edges(tmp_path: Path) -> None:
    f = _make_file(tmp_path, "models.py", "class User:\n    pass\n")

    result = analyze_python_files([f], tmp_path)

    cls_edges = [e for e in result.edges if e.rel_type == "DEFINES_CLASS"]
    assert len(cls_edges) == 1
    assert cls_edges[0].source_path == "models.py"
    assert cls_edges[0].target_path == "User"


def test_has_method_edges(tmp_path: Path) -> None:
    code = "class Foo:\n    def bar(self):\n        pass\n"
    f = _make_file(tmp_path, "foo.py", code)

    result = analyze_python_files([f], tmp_path)

    method_edges = [e for e in result.edges if e.rel_type == "HAS_METHOD"]
    assert len(method_edges) == 1
    assert method_edges[0].source_label == "Foo"
    assert method_edges[0].target_path == "bar"


# -- Function call resolution ---------------------------------------------


def test_function_calls_same_file(tmp_path: Path) -> None:
    code = "def a():\n    b()\n\ndef b():\n    pass\n"
    f = _make_file(tmp_path, "logic.py", code)

    result = analyze_python_files([f], tmp_path)

    call_edges = [e for e in result.edges if e.rel_type == "CALLS"]
    assert len(call_edges) == 1
    assert call_edges[0].source_label == "a"
    assert call_edges[0].target_label == "b"


# -- Error handling --------------------------------------------------------


def test_syntax_error_file_is_skipped(tmp_path: Path) -> None:
    bad = _make_file(tmp_path, "broken.py", "def oops(:\n    pass\n")
    good = _make_file(tmp_path, "ok.py", "def fine():\n    pass\n")

    result = analyze_python_files([bad, good], tmp_path)

    assert len(result.functions) == 1
    assert result.functions[0].name == "fine"


def test_empty_python_file(tmp_path: Path) -> None:
    f = _make_file(tmp_path, "empty.py", "")

    result = analyze_python_files([f], tmp_path)

    assert result.functions == []
    assert result.classes == []


# -- Integration with index_repository ------------------------------------


def test_index_with_python_analysis(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("def run():\n    pass\n\nclass App:\n    def start(self):\n        pass\n")
    (tmp_path / "README.md").write_text("# readme")

    result = index_repository(tmp_path, analyze_python=True)

    assert len(result.functions) >= 2  # run, start
    assert len(result.classes) >= 1    # App
    assert len(result.directories) >= 1
    assert len(result.files) >= 2


def test_index_without_python_analysis(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def hello():\n    pass\n")

    result = index_repository(tmp_path, analyze_python=False)

    assert result.functions == []
    assert result.classes == []
