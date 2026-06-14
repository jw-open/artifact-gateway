"""Tests for artifact_gateway.files."""
from __future__ import annotations

import pytest

from artifact_gateway.files import FilesHandler

USER = "user-abc"
SESSION = "sess-001"


@pytest.fixture()
def handler(tmp_path):
    return FilesHandler(root=str(tmp_path))


async def test_write_then_read_user_scope(handler):
    await handler.write("user", USER, "notes/todo.txt", "hello world")
    out = await handler.read("user", USER, "notes/todo.txt")
    assert out["content"] == "hello world"
    assert out["path"] == "notes/todo.txt"


async def test_write_reports_bytes(handler):
    res = await handler.write("user", USER, "a.txt", "abc")
    assert res["bytes"] == 3


async def test_session_scope_isolated_from_user_scope(handler):
    await handler.write("user", USER, "x.txt", "user-data")
    await handler.write("session", USER, "x.txt", "session-data", session_id=SESSION)
    assert (await handler.read("user", USER, "x.txt"))["content"] == "user-data"
    assert (
        await handler.read("session", USER, "x.txt", session_id=SESSION)
    )["content"] == "session-data"


async def test_list_returns_entries(handler):
    await handler.write("user", USER, "dir/a.txt", "1")
    await handler.write("user", USER, "dir/b.txt", "22")
    listing = await handler.list("user", USER, "dir")
    names = {e["name"] for e in listing["entries"]}
    assert names == {"a.txt", "b.txt"}


async def test_list_missing_dir_returns_empty(handler):
    listing = await handler.list("user", USER, "nope")
    assert listing["entries"] == []


async def test_delete_file(handler):
    await handler.write("user", USER, "gone.txt", "x")
    res = await handler.delete("user", USER, "gone.txt")
    assert res["deleted"] is True
    with pytest.raises(FileNotFoundError):
        await handler.read("user", USER, "gone.txt")


async def test_read_missing_file_raises(handler):
    with pytest.raises(FileNotFoundError):
        await handler.read("user", USER, "missing.txt")


async def test_path_traversal_rejected(handler):
    with pytest.raises(ValueError, match="escapes"):
        await handler.write("user", USER, "../../etc/passwd", "evil")


async def test_traversal_via_read_rejected(handler):
    with pytest.raises(ValueError, match="escapes"):
        await handler.read("user", USER, "../../../etc/hosts")


async def test_session_scope_requires_session_id(handler):
    with pytest.raises(ValueError, match="session_id is required"):
        await handler.write("session", USER, "x.txt", "data")


async def test_max_file_size_enforced(tmp_path):
    small = FilesHandler(root=str(tmp_path), max_file_bytes=4)
    with pytest.raises(ValueError, match="max size"):
        await small.write("user", USER, "big.txt", "too long")


async def test_users_cannot_collide(handler):
    await handler.write("user", "alice", "shared.txt", "alice")
    await handler.write("user", "bob", "shared.txt", "bob")
    assert (await handler.read("user", "alice", "shared.txt"))["content"] == "alice"
    assert (await handler.read("user", "bob", "shared.txt"))["content"] == "bob"
