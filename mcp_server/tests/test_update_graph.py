"""Tests for the brocode_update_graph tool.

Covers: input validation (empty codebase, empty changes, invalid action,
invalid node_type, missing required fields), upsert/delete dispatch for
each node type, default value derivation, batch operations (all succeed,
partial failure, all fail).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from brocode_mcp.server import brocode_update_graph as _tool

# Access the underlying async function, bypassing FastMCP's FunctionTool wrapper.
update_graph = _tool.fn


# ===================================================================
# Validation
# ===================================================================


@pytest.mark.asyncio
async def test_empty_codebase_name(mock_db, mock_ctx):
    """Empty codebase_name should return an error."""
    result = await update_graph(
        codebase_name="",
        changes=[{"action": "upsert", "node_type": "File", "path": "src/app.py"}],
        ctx=mock_ctx,
    )
    assert result["status"] == "error"
    assert "codebase_name" in result["message"].lower()


@pytest.mark.asyncio
async def test_empty_changes_list(mock_db, mock_ctx):
    """Empty changes list should return an error."""
    result = await update_graph(
        codebase_name="my-repo",
        changes=[],
        ctx=mock_ctx,
    )
    assert result["status"] == "error"
    assert "changes" in result["message"].lower()


@pytest.mark.asyncio
async def test_invalid_action(mock_db, mock_ctx):
    """Invalid action should produce an error for that change."""
    result = await update_graph(
        codebase_name="my-repo",
        changes=[{"action": "merge", "node_type": "File", "path": "src/app.py"}],
        ctx=mock_ctx,
    )
    assert result["status"] == "error"
    assert len(result["errors"]) == 1
    assert "action" in result["errors"][0].lower()


@pytest.mark.asyncio
async def test_invalid_node_type(mock_db, mock_ctx):
    """Invalid node_type should produce an error for that change."""
    result = await update_graph(
        codebase_name="my-repo",
        changes=[{"action": "upsert", "node_type": "Module", "path": "src/app.py"}],
        ctx=mock_ctx,
    )
    assert result["status"] == "error"
    assert len(result["errors"]) == 1
    assert "node_type" in result["errors"][0].lower()


@pytest.mark.asyncio
async def test_missing_action_field(mock_db, mock_ctx):
    """Missing 'action' field should produce an error."""
    result = await update_graph(
        codebase_name="my-repo",
        changes=[{"node_type": "File", "path": "src/app.py"}],
        ctx=mock_ctx,
    )
    assert result["status"] == "error"
    assert len(result["errors"]) == 1
    assert "action" in result["errors"][0].lower()


@pytest.mark.asyncio
async def test_missing_node_type_field(mock_db, mock_ctx):
    """Missing 'node_type' field should produce an error."""
    result = await update_graph(
        codebase_name="my-repo",
        changes=[{"action": "upsert", "path": "src/app.py"}],
        ctx=mock_ctx,
    )
    assert result["status"] == "error"
    assert len(result["errors"]) == 1
    assert "node_type" in result["errors"][0].lower()


@pytest.mark.asyncio
async def test_missing_path_for_file_upsert(mock_db, mock_ctx):
    """Upsert File without 'path' should produce an error."""
    result = await update_graph(
        codebase_name="my-repo",
        changes=[{"action": "upsert", "node_type": "File"}],
        ctx=mock_ctx,
    )
    assert result["status"] == "error"
    assert len(result["errors"]) == 1
    assert "path" in result["errors"][0].lower()


@pytest.mark.asyncio
async def test_missing_path_for_directory_upsert(mock_db, mock_ctx):
    """Upsert Directory without 'path' should produce an error."""
    result = await update_graph(
        codebase_name="my-repo",
        changes=[{"action": "upsert", "node_type": "Directory"}],
        ctx=mock_ctx,
    )
    assert result["status"] == "error"
    assert len(result["errors"]) == 1
    assert "path" in result["errors"][0].lower()


@pytest.mark.asyncio
async def test_missing_file_path_for_function_upsert(mock_db, mock_ctx):
    """Upsert Function without 'file_path' should produce an error."""
    result = await update_graph(
        codebase_name="my-repo",
        changes=[{"action": "upsert", "node_type": "Function", "function_name": "foo"}],
        ctx=mock_ctx,
    )
    assert result["status"] == "error"
    assert len(result["errors"]) == 1
    assert "file_path" in result["errors"][0].lower()


@pytest.mark.asyncio
async def test_missing_function_name_for_function_upsert(mock_db, mock_ctx):
    """Upsert Function without 'function_name' should produce an error."""
    result = await update_graph(
        codebase_name="my-repo",
        changes=[{"action": "upsert", "node_type": "Function", "file_path": "src/app.py"}],
        ctx=mock_ctx,
    )
    assert result["status"] == "error"
    assert len(result["errors"]) == 1
    assert "function_name" in result["errors"][0].lower()


@pytest.mark.asyncio
async def test_missing_file_path_for_class_upsert(mock_db, mock_ctx):
    """Upsert Class without 'file_path' should produce an error."""
    result = await update_graph(
        codebase_name="my-repo",
        changes=[{"action": "upsert", "node_type": "Class", "class_name": "Foo"}],
        ctx=mock_ctx,
    )
    assert result["status"] == "error"
    assert len(result["errors"]) == 1
    assert "file_path" in result["errors"][0].lower()


@pytest.mark.asyncio
async def test_missing_class_name_for_class_upsert(mock_db, mock_ctx):
    """Upsert Class without 'class_name' should produce an error."""
    result = await update_graph(
        codebase_name="my-repo",
        changes=[{"action": "upsert", "node_type": "Class", "file_path": "src/app.py"}],
        ctx=mock_ctx,
    )
    assert result["status"] == "error"
    assert len(result["errors"]) == 1
    assert "class_name" in result["errors"][0].lower()


# ===================================================================
# Upsert Dispatch
# ===================================================================


@pytest.mark.asyncio
async def test_upsert_file(mock_db, mock_ctx):
    """Upsert File should call db.upsert_file with correct args."""
    result = await update_graph(
        codebase_name="my-repo",
        changes=[{
            "action": "upsert",
            "node_type": "File",
            "path": "src/app.py",
            "size_bytes": 1024,
            "parent_path": "src",
        }],
        ctx=mock_ctx,
    )
    assert result["status"] == "ok"
    assert result["applied"] == 1
    mock_db.upsert_file.assert_awaited_once_with(
        codebase="my-repo",
        path="src/app.py",
        name="app.py",
        extension=".py",
        size_bytes=1024,
        parent_path="src",
    )


@pytest.mark.asyncio
async def test_upsert_file_defaults(mock_db, mock_ctx):
    """Upsert File with only 'path' should derive name, extension, and default size_bytes=0."""
    result = await update_graph(
        codebase_name="my-repo",
        changes=[{
            "action": "upsert",
            "node_type": "File",
            "path": "README.md",
        }],
        ctx=mock_ctx,
    )
    assert result["status"] == "ok"
    mock_db.upsert_file.assert_awaited_once_with(
        codebase="my-repo",
        path="README.md",
        name="README.md",
        extension=".md",
        size_bytes=0,
        parent_path="",
    )


@pytest.mark.asyncio
async def test_upsert_file_explicit_name(mock_db, mock_ctx):
    """Upsert File with explicit name should use that instead of deriving."""
    result = await update_graph(
        codebase_name="my-repo",
        changes=[{
            "action": "upsert",
            "node_type": "File",
            "path": "src/app.py",
            "name": "custom-name.py",
        }],
        ctx=mock_ctx,
    )
    assert result["status"] == "ok"
    mock_db.upsert_file.assert_awaited_once_with(
        codebase="my-repo",
        path="src/app.py",
        name="custom-name.py",
        extension=".py",
        size_bytes=0,
        parent_path="",
    )


@pytest.mark.asyncio
async def test_upsert_directory(mock_db, mock_ctx):
    """Upsert Directory should call db.upsert_directory with correct args."""
    result = await update_graph(
        codebase_name="my-repo",
        changes=[{
            "action": "upsert",
            "node_type": "Directory",
            "path": "src/utils",
            "depth": 2,
            "parent_path": "src",
        }],
        ctx=mock_ctx,
    )
    assert result["status"] == "ok"
    mock_db.upsert_directory.assert_awaited_once_with(
        codebase="my-repo",
        path="src/utils",
        name="utils",
        depth=2,
        parent_path="src",
    )


@pytest.mark.asyncio
async def test_upsert_directory_defaults(mock_db, mock_ctx):
    """Upsert Directory with only 'path' should derive name and default depth=0."""
    result = await update_graph(
        codebase_name="my-repo",
        changes=[{
            "action": "upsert",
            "node_type": "Directory",
            "path": "src",
        }],
        ctx=mock_ctx,
    )
    assert result["status"] == "ok"
    mock_db.upsert_directory.assert_awaited_once_with(
        codebase="my-repo",
        path="src",
        name="src",
        depth=0,
        parent_path="",
    )


@pytest.mark.asyncio
async def test_upsert_function(mock_db, mock_ctx):
    """Upsert Function should call db.upsert_function with correct args."""
    result = await update_graph(
        codebase_name="my-repo",
        changes=[{
            "action": "upsert",
            "node_type": "Function",
            "file_path": "src/app.py",
            "function_name": "main",
            "line_number": 10,
            "is_method": False,
            "parameters": "self, x: int",
            "owner_class": "",
        }],
        ctx=mock_ctx,
    )
    assert result["status"] == "ok"
    mock_db.upsert_function.assert_awaited_once_with(
        codebase="my-repo",
        file_path="src/app.py",
        name="main",
        line_number=10,
        is_method=False,
        parameters="self, x: int",
        owner_class="",
    )


@pytest.mark.asyncio
async def test_upsert_function_defaults(mock_db, mock_ctx):
    """Upsert Function with minimal fields should use defaults."""
    result = await update_graph(
        codebase_name="my-repo",
        changes=[{
            "action": "upsert",
            "node_type": "Function",
            "file_path": "src/app.py",
            "function_name": "main",
        }],
        ctx=mock_ctx,
    )
    assert result["status"] == "ok"
    mock_db.upsert_function.assert_awaited_once_with(
        codebase="my-repo",
        file_path="src/app.py",
        name="main",
        line_number=0,
        is_method=False,
        parameters="",
        owner_class="",
    )


@pytest.mark.asyncio
async def test_upsert_class(mock_db, mock_ctx):
    """Upsert Class should call db.upsert_class with correct args."""
    result = await update_graph(
        codebase_name="my-repo",
        changes=[{
            "action": "upsert",
            "node_type": "Class",
            "file_path": "src/models.py",
            "class_name": "User",
            "line_number": 5,
            "base_classes": "BaseModel, Mixin",
        }],
        ctx=mock_ctx,
    )
    assert result["status"] == "ok"
    mock_db.upsert_class.assert_awaited_once_with(
        codebase="my-repo",
        file_path="src/models.py",
        name="User",
        line_number=5,
        base_classes="BaseModel, Mixin",
    )


@pytest.mark.asyncio
async def test_upsert_class_defaults(mock_db, mock_ctx):
    """Upsert Class with minimal fields should use defaults."""
    result = await update_graph(
        codebase_name="my-repo",
        changes=[{
            "action": "upsert",
            "node_type": "Class",
            "file_path": "src/models.py",
            "class_name": "User",
        }],
        ctx=mock_ctx,
    )
    assert result["status"] == "ok"
    mock_db.upsert_class.assert_awaited_once_with(
        codebase="my-repo",
        file_path="src/models.py",
        name="User",
        line_number=0,
        base_classes="",
    )


# ===================================================================
# Delete Dispatch
# ===================================================================


@pytest.mark.asyncio
async def test_delete_file(mock_db, mock_ctx):
    """Delete File should call db.delete_file."""
    result = await update_graph(
        codebase_name="my-repo",
        changes=[{"action": "delete", "node_type": "File", "path": "src/old.py"}],
        ctx=mock_ctx,
    )
    assert result["status"] == "ok"
    assert result["applied"] == 1
    mock_db.delete_file.assert_awaited_once_with(path="src/old.py", codebase="my-repo")


@pytest.mark.asyncio
async def test_delete_directory(mock_db, mock_ctx):
    """Delete Directory should call db.delete_directory."""
    result = await update_graph(
        codebase_name="my-repo",
        changes=[{"action": "delete", "node_type": "Directory", "path": "src/old"}],
        ctx=mock_ctx,
    )
    assert result["status"] == "ok"
    mock_db.delete_directory.assert_awaited_once_with(
        path="src/old", codebase="my-repo"
    )


@pytest.mark.asyncio
async def test_delete_function(mock_db, mock_ctx):
    """Delete Function should call db.delete_function."""
    result = await update_graph(
        codebase_name="my-repo",
        changes=[{
            "action": "delete",
            "node_type": "Function",
            "file_path": "src/app.py",
            "function_name": "old_func",
        }],
        ctx=mock_ctx,
    )
    assert result["status"] == "ok"
    mock_db.delete_function.assert_awaited_once_with(
        file_path="src/app.py", name="old_func", codebase="my-repo"
    )


@pytest.mark.asyncio
async def test_delete_class(mock_db, mock_ctx):
    """Delete Class should call db.delete_class."""
    result = await update_graph(
        codebase_name="my-repo",
        changes=[{
            "action": "delete",
            "node_type": "Class",
            "file_path": "src/models.py",
            "class_name": "OldModel",
        }],
        ctx=mock_ctx,
    )
    assert result["status"] == "ok"
    mock_db.delete_class.assert_awaited_once_with(
        file_path="src/models.py", name="OldModel", codebase="my-repo"
    )


# ===================================================================
# Batch Operations
# ===================================================================


@pytest.mark.asyncio
async def test_batch_all_succeed(mock_db, mock_ctx):
    """Multiple valid changes should all be applied."""
    result = await update_graph(
        codebase_name="my-repo",
        changes=[
            {"action": "upsert", "node_type": "File", "path": "src/a.py"},
            {"action": "upsert", "node_type": "File", "path": "src/b.py"},
            {"action": "delete", "node_type": "File", "path": "src/c.py"},
        ],
        ctx=mock_ctx,
    )
    assert result["status"] == "ok"
    assert result["applied"] == 3
    assert result["errors"] == []


@pytest.mark.asyncio
async def test_batch_partial_failure(mock_db, mock_ctx):
    """A mix of valid and invalid changes should apply valid ones and report errors."""
    mock_db.upsert_file.side_effect = [None, Exception("DB error")]

    result = await update_graph(
        codebase_name="my-repo",
        changes=[
            {"action": "upsert", "node_type": "File", "path": "src/a.py"},
            {"action": "upsert", "node_type": "File", "path": "src/b.py"},
        ],
        ctx=mock_ctx,
    )
    assert result["status"] == "partial"
    assert result["applied"] == 1
    assert len(result["errors"]) == 1
    assert "DB error" in result["errors"][0]


@pytest.mark.asyncio
async def test_batch_all_fail(mock_db, mock_ctx):
    """When all changes fail, status should be 'error'."""
    mock_db.upsert_file.side_effect = Exception("DB error")

    result = await update_graph(
        codebase_name="my-repo",
        changes=[
            {"action": "upsert", "node_type": "File", "path": "src/a.py"},
            {"action": "upsert", "node_type": "File", "path": "src/b.py"},
        ],
        ctx=mock_ctx,
    )
    assert result["status"] == "error"
    assert result["applied"] == 0
    assert len(result["errors"]) == 2


@pytest.mark.asyncio
async def test_batch_validation_errors_mixed_with_success(mock_db, mock_ctx):
    """Validation errors for some changes shouldn't prevent valid changes from applying."""
    result = await update_graph(
        codebase_name="my-repo",
        changes=[
            {"action": "upsert", "node_type": "File", "path": "src/a.py"},
            {"action": "invalid", "node_type": "File", "path": "src/b.py"},
            {"action": "upsert", "node_type": "File", "path": "src/c.py"},
        ],
        ctx=mock_ctx,
    )
    assert result["status"] == "partial"
    assert result["applied"] == 2
    assert len(result["errors"]) == 1
