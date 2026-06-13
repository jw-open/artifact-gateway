"""Tests for artifact_gateway.db.duckdb.DuckDBHandler."""
from __future__ import annotations

from pathlib import Path

import pytest

from artifact_gateway.db.duckdb import DuckDBHandler, SCOPE_USER, SCOPE_SESSION

USER_ID = "user-abc123"
SESSION_ID = "sess-xyz789"
DB_NAME = "mydb"


@pytest.fixture()
def handler(tmp_path: Path) -> DuckDBHandler:
    return DuckDBHandler(workspace=str(tmp_path))


# --- _db_path() ---

def test_db_path_user_scope(handler: DuckDBHandler, tmp_path: Path):
    p = handler._db_path(SCOPE_USER, USER_ID, DB_NAME)
    expected = tmp_path / USER_ID / "db" / f"{DB_NAME}.duckdb"
    assert p == expected


def test_db_path_session_scope(handler: DuckDBHandler, tmp_path: Path):
    p = handler._db_path(SCOPE_SESSION, USER_ID, DB_NAME, session_id=SESSION_ID)
    expected = (
        tmp_path / USER_ID / "sessions" / SESSION_ID / "db" / f"{DB_NAME}.duckdb"
    )
    assert p == expected


def test_db_path_session_scope_requires_session_id(handler: DuckDBHandler):
    with pytest.raises(ValueError, match="session_id"):
        handler._db_path(SCOPE_SESSION, USER_ID, DB_NAME)


# --- query() ---

async def test_query_creates_file_and_returns_results(
    handler: DuckDBHandler, tmp_path: Path
):
    await handler.exec(SCOPE_USER, USER_ID, DB_NAME, "CREATE TABLE t (id INT, val TEXT)")
    await handler.exec(SCOPE_USER, USER_ID, DB_NAME, "INSERT INTO t VALUES (1, 'hello'), (2, 'world')")
    result = await handler.query(SCOPE_USER, USER_ID, DB_NAME, "SELECT * FROM t ORDER BY id")
    assert result["columns"] == ["id", "val"]
    assert result["rows"] == [[1, "hello"], [2, "world"]]
    assert result["rowcount"] == 2


async def test_query_file_is_created_on_disk(handler: DuckDBHandler, tmp_path: Path):
    await handler.exec(SCOPE_USER, USER_ID, DB_NAME, "CREATE TABLE x (n INT)")
    db_file = tmp_path / USER_ID / "db" / f"{DB_NAME}.duckdb"
    assert db_file.exists()


async def test_query_returns_empty_for_no_rows(handler: DuckDBHandler):
    await handler.exec(SCOPE_USER, USER_ID, DB_NAME, "CREATE TABLE empty (n INT)")
    result = await handler.query(SCOPE_USER, USER_ID, DB_NAME, "SELECT * FROM empty")
    assert result["columns"] == ["n"]
    assert result["rows"] == []
    assert result["rowcount"] == 0


# --- exec() ---

async def test_exec_returns_success_true(handler: DuckDBHandler):
    result = await handler.exec(SCOPE_USER, USER_ID, DB_NAME, "CREATE TABLE s (n INT)")
    assert result == {"success": True}


async def test_exec_and_query_use_correct_file_path_user(
    handler: DuckDBHandler, tmp_path: Path
):
    await handler.exec(SCOPE_USER, USER_ID, "db1", "CREATE TABLE t (n INT)")
    await handler.exec(SCOPE_USER, USER_ID, "db1", "INSERT INTO t VALUES (42)")
    result = await handler.query(SCOPE_USER, USER_ID, "db1", "SELECT n FROM t")
    assert result["rows"] == [[42]]


async def test_exec_and_query_use_correct_file_path_session(
    handler: DuckDBHandler, tmp_path: Path
):
    await handler.exec(
        SCOPE_SESSION, USER_ID, DB_NAME, "CREATE TABLE t (n INT)",
        session_id=SESSION_ID,
    )
    await handler.exec(
        SCOPE_SESSION, USER_ID, DB_NAME, "INSERT INTO t VALUES (99)",
        session_id=SESSION_ID,
    )
    result = await handler.query(
        SCOPE_SESSION, USER_ID, DB_NAME, "SELECT n FROM t",
        session_id=SESSION_ID,
    )
    assert result["rows"] == [[99]]


async def test_user_and_session_dbs_are_isolated(handler: DuckDBHandler):
    # Write to user-scoped DB.
    await handler.exec(SCOPE_USER, USER_ID, DB_NAME, "CREATE TABLE t (n INT)")
    await handler.exec(SCOPE_USER, USER_ID, DB_NAME, "INSERT INTO t VALUES (1)")

    # Session-scoped DB starts empty.
    await handler.exec(
        SCOPE_SESSION, USER_ID, DB_NAME, "CREATE TABLE t (n INT)",
        session_id=SESSION_ID,
    )
    result = await handler.query(
        SCOPE_SESSION, USER_ID, DB_NAME, "SELECT n FROM t",
        session_id=SESSION_ID,
    )
    assert result["rows"] == []


async def test_exec_with_params(handler: DuckDBHandler):
    await handler.exec(SCOPE_USER, USER_ID, DB_NAME, "CREATE TABLE p (n INT, s TEXT)")
    await handler.exec(
        SCOPE_USER, USER_ID, DB_NAME,
        "INSERT INTO p VALUES (?, ?)",
        params=[7, "hello"],
    )
    result = await handler.query(SCOPE_USER, USER_ID, DB_NAME, "SELECT * FROM p")
    assert result["rows"] == [[7, "hello"]]
