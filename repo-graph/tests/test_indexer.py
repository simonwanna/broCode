from pathlib import Path

from repo_graph.indexer.filesystem import index_repository, _is_ignored
from repo_graph.models.nodes import Codebase, Directory, File


def test_index_simple_tree(tmp_path: Path) -> None:
    # Build a small file tree:
    #   root/
    #     src/
    #       main.py
    #     README.md
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')")
    (tmp_path / "README.md").write_text("# readme")

    result = index_repository(tmp_path)

    assert result.codebase.name == tmp_path.name
    assert result.codebase.root_path == str(tmp_path)

    dir_names = [d.name for d in result.directories]
    assert "src" in dir_names

    file_names = [f.name for f in result.files]
    assert "main.py" in file_names
    assert "README.md" in file_names

    # Edges: root->src (CONTAINS_DIR), root->README.md (CONTAINS_FILE),
    #         src->main.py (CONTAINS_FILE)
    assert len(result.edges) == 3

    rel_types = {e.rel_type for e in result.edges}
    assert rel_types == {"CONTAINS_DIR", "CONTAINS_FILE"}


def test_ignores_git_and_pycache(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "foo.pyc").write_bytes(b"\x00")
    (tmp_path / "app.py").write_text("pass")

    result = index_repository(tmp_path)

    all_paths = [d.path for d in result.directories] + [f.path for f in result.files]
    assert not any(".git" in p for p in all_paths)
    assert not any("__pycache__" in p for p in all_paths)
    assert "app.py" in [f.name for f in result.files]


def test_file_node_attributes(tmp_path: Path) -> None:
    content = "hello world"
    (tmp_path / "data.txt").write_text(content)

    result = index_repository(tmp_path)

    f = result.files[0]
    assert f.name == "data.txt"
    assert f.extension == ".txt"
    assert f.size_bytes == len(content)
    assert f.path == "data.txt"


def test_nested_directories(tmp_path: Path) -> None:
    (tmp_path / "a" / "b" / "c").mkdir(parents=True)
    (tmp_path / "a" / "b" / "c" / "deep.py").write_text("")

    result = index_repository(tmp_path)

    depths = {d.name: d.depth for d in result.directories}
    assert depths["a"] == 1
    assert depths["b"] == 2
    assert depths["c"] == 3


# --- .indexignore tests ---


def test_indexignore_exact_filename(tmp_path: Path) -> None:
    (tmp_path / ".indexignore").write_text("secret.env\n")
    (tmp_path / "secret.env").write_text("KEY=val")
    (tmp_path / "app.py").write_text("pass")

    result = index_repository(tmp_path)
    file_names = [f.name for f in result.files]
    assert "secret.env" not in file_names
    assert "app.py" in file_names


def test_indexignore_glob_extension(tmp_path: Path) -> None:
    (tmp_path / ".indexignore").write_text("*.log\n")
    (tmp_path / "debug.log").write_text("log")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "server.log").write_text("log")
    (tmp_path / "app.py").write_text("pass")

    result = index_repository(tmp_path)
    file_names = [f.name for f in result.files]
    assert "debug.log" not in file_names
    assert "server.log" not in file_names
    assert "app.py" in file_names


def test_indexignore_directory_pattern(tmp_path: Path) -> None:
    (tmp_path / ".indexignore").write_text("build/**\n")
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "output.js").write_text("")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("")

    result = index_repository(tmp_path)
    all_paths = [d.path for d in result.directories] + [f.path for f in result.files]
    assert not any("build" in p for p in all_paths)
    assert "src" in [d.name for d in result.directories]


def test_indexignore_doublestar_prefix(tmp_path: Path) -> None:
    (tmp_path / ".indexignore").write_text("**/test_*\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_foo.py").write_text("")
    (tmp_path / "test_bar.py").write_text("")
    (tmp_path / "app.py").write_text("")

    result = index_repository(tmp_path)
    file_names = [f.name for f in result.files]
    assert "test_foo.py" not in file_names
    assert "test_bar.py" not in file_names
    assert "app.py" in file_names


def test_indexignore_comments_and_blanks(tmp_path: Path) -> None:
    (tmp_path / ".indexignore").write_text("# this is a comment\n\n*.tmp\n")
    (tmp_path / "data.tmp").write_text("")
    (tmp_path / "app.py").write_text("")

    result = index_repository(tmp_path)
    file_names = [f.name for f in result.files]
    assert "data.tmp" not in file_names
    assert "app.py" in file_names


def test_no_indexignore_file(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("pass")
    (tmp_path / "data.log").write_text("log")

    result = index_repository(tmp_path)
    file_names = [f.name for f in result.files]
    assert "app.py" in file_names
    assert "data.log" in file_names
