"""Tests for artifact_gateway.db.mongo.MongoHandler."""
from __future__ import annotations

import pytest
import mongomock_motor

from artifact_gateway.db.mongo import MongoHandler, SCOPE_USER, SCOPE_SESSION

USER_ID = "user-abc123"
SESSION_ID = "sess-xyz789"
COLLECTION = "notes"


@pytest.fixture()
def motor_db():
    """Return a mongomock-motor async database for testing."""
    client = mongomock_motor.AsyncMongoMockClient()
    return client["testdb"]


@pytest.fixture()
def handler(motor_db) -> MongoHandler:
    return MongoHandler(db=motor_db)


# --- _collection_name() ---

def test_collection_name_user_scope(handler: MongoHandler):
    name = handler._collection_name(SCOPE_USER, USER_ID, COLLECTION)
    assert name == f"app_user_{USER_ID}_{COLLECTION}"


def test_collection_name_session_scope(handler: MongoHandler):
    name = handler._collection_name(SCOPE_SESSION, USER_ID, COLLECTION, session_id=SESSION_ID)
    assert name == f"app_session_{SESSION_ID}_{COLLECTION}"


def test_collection_name_session_scope_requires_session_id(handler: MongoHandler):
    with pytest.raises(ValueError, match="session_id"):
        handler._collection_name(SCOPE_SESSION, USER_ID, COLLECTION)


# --- find() ---

async def test_find_returns_empty_list_when_no_docs(handler: MongoHandler):
    docs = await handler.find(SCOPE_USER, USER_ID, COLLECTION, filter={})
    assert docs == []


async def test_find_returns_matching_documents(handler: MongoHandler, motor_db):
    col_name = f"app_user_{USER_ID}_{COLLECTION}"
    await motor_db[col_name].insert_many([
        {"text": "hello", "status": "active"},
        {"text": "world", "status": "inactive"},
    ])
    docs = await handler.find(SCOPE_USER, USER_ID, COLLECTION, filter={"status": "active"})
    assert len(docs) == 1
    assert docs[0]["text"] == "hello"


async def test_find_serialises_object_id_as_string(handler: MongoHandler, motor_db):
    col_name = f"app_user_{USER_ID}_{COLLECTION}"
    await motor_db[col_name].insert_one({"text": "test"})
    docs = await handler.find(SCOPE_USER, USER_ID, COLLECTION)
    assert isinstance(docs[0]["_id"], str)


async def test_find_respects_limit(handler: MongoHandler, motor_db):
    col_name = f"app_user_{USER_ID}_{COLLECTION}"
    await motor_db[col_name].insert_many([{"n": i} for i in range(10)])
    docs = await handler.find(SCOPE_USER, USER_ID, COLLECTION, limit=3)
    assert len(docs) == 3


async def test_find_session_scope_uses_correct_collection(
    handler: MongoHandler, motor_db
):
    col_name = f"app_session_{SESSION_ID}_{COLLECTION}"
    await motor_db[col_name].insert_one({"key": "val"})
    docs = await handler.find(
        SCOPE_SESSION, USER_ID, COLLECTION, session_id=SESSION_ID
    )
    assert len(docs) == 1
    assert docs[0]["key"] == "val"


# --- upsert() ---

async def test_upsert_inserts_new_document(handler: MongoHandler):
    result = await handler.upsert(
        SCOPE_USER, USER_ID, COLLECTION,
        filter={"key": "unique-key"},
        update={"$set": {"value": 42}},
    )
    assert result["upserted"] is True
    assert result["matched"] == 0


async def test_upsert_updates_existing_document(handler: MongoHandler, motor_db):
    col_name = f"app_user_{USER_ID}_{COLLECTION}"
    await motor_db[col_name].insert_one({"key": "k1", "value": 1})
    result = await handler.upsert(
        SCOPE_USER, USER_ID, COLLECTION,
        filter={"key": "k1"},
        update={"$set": {"value": 99}},
    )
    assert result["upserted"] is False
    assert result["matched"] == 1
    doc = await motor_db[col_name].find_one({"key": "k1"})
    assert doc["value"] == 99


async def test_upsert_session_scope(handler: MongoHandler):
    result = await handler.upsert(
        SCOPE_SESSION, USER_ID, COLLECTION,
        filter={"key": "s-key"},
        update={"$set": {"data": "session-data"}},
        session_id=SESSION_ID,
    )
    assert result["upserted"] is True


# --- delete() ---

async def test_delete_removes_matching_documents(handler: MongoHandler, motor_db):
    col_name = f"app_user_{USER_ID}_{COLLECTION}"
    await motor_db[col_name].insert_many([
        {"status": "done"},
        {"status": "done"},
        {"status": "active"},
    ])
    result = await handler.delete(
        SCOPE_USER, USER_ID, COLLECTION, filter={"status": "done"}
    )
    assert result["deleted"] == 2


async def test_delete_returns_zero_when_no_match(handler: MongoHandler):
    result = await handler.delete(
        SCOPE_USER, USER_ID, COLLECTION, filter={"status": "nonexistent"}
    )
    assert result == {"deleted": 0}


async def test_delete_session_scope(handler: MongoHandler, motor_db):
    col_name = f"app_session_{SESSION_ID}_{COLLECTION}"
    await motor_db[col_name].insert_one({"key": "to-delete"})
    result = await handler.delete(
        SCOPE_SESSION, USER_ID, COLLECTION,
        filter={"key": "to-delete"},
        session_id=SESSION_ID,
    )
    assert result["deleted"] == 1
