"""Shared-collection state + event-log store (the recommended store for live app state).

Unlike :class:`~artifact_gateway.db.mongo.MongoHandler` (one collection per tenant,
free-form documents), this store uses TWO single, shared collections and isolates
tenants at the document level via a ``tenant`` field that the gateway derives from
token claims — never from app input:

* ``app_state``  — current state, one doc per ``(tenant, ns, resource_id)``,
  upserted in place with an incrementing ``version``. Cheap reads, immediate writes.
* ``app_events`` — append-only activity log, one immutable doc per change.

Granularity: current state at the resource level (``app_state``); history at the
resource-activity level (``app_events``). This is the "current-state table + event
log" (CQRS-lite) pattern — avoid storing one giant snapshot document per tenant.
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

STATE_COLLECTION = "app_state"
EVENTS_COLLECTION = "app_events"


class VersionConflict(Exception):
    """Raised when an optimistic-concurrency ``expected_version`` check fails."""

    def __init__(self, current_version: int) -> None:
        super().__init__(f"version conflict (current={current_version})")
        self.current_version = current_version


class StateStore:
    """Per-resource current-state docs + an append-only event log, document-isolated.

    Pass a Motor ``AsyncIOMotorDatabase`` at construction. ``tenant`` is supplied by
    the caller from validated token claims (e.g. ``f"account:{account_id}"``); app
    code never provides it.
    """

    def __init__(self, db: Any) -> None:
        self._db = db

    async def ensure_indexes(self) -> None:
        """Create the unique current-state index and the event-log index (idempotent)."""
        await self._db[STATE_COLLECTION].create_index(
            [("tenant", 1), ("ns", 1), ("resource_id", 1)], unique=True, name="tenant_ns_resource")
        await self._db[EVENTS_COLLECTION].create_index(
            [("tenant", 1), ("ns", 1), ("resource_id", 1), ("ts", -1)], name="tenant_ns_resource_ts")

    async def set(
        self,
        tenant: str,
        ns: str,
        resource_id: str,
        patch: Dict[str, Any],
        expected_version: Optional[int] = None,
        event: bool = True,
    ) -> Dict[str, Any]:
        """Merge ``patch`` into the resource's current state and bump its version.

        Raises:
            VersionConflict: If ``expected_version`` is given and does not match.
        """
        now = datetime.now(timezone.utc)
        key = {"tenant": tenant, "ns": ns, "resource_id": str(resource_id)}
        current = await self._db[STATE_COLLECTION].find_one(key, {"version": 1})
        cur_ver = int((current or {}).get("version", 0))
        if expected_version is not None and int(expected_version) != cur_ver:
            raise VersionConflict(cur_ver)
        new_ver = cur_ver + 1
        set_fields: Dict[str, Any] = {f"data.{k}": v for k, v in (patch or {}).items()}
        set_fields.update({"version": new_ver, "updated_at": now, **key})
        await self._db[STATE_COLLECTION].update_one(
            key, {"$set": set_fields, "$setOnInsert": {"created_at": now}}, upsert=True)
        if event:
            await self._db[EVENTS_COLLECTION].insert_one({
                "_id": str(uuid.uuid4()), **key, "op": "set",
                "patch": patch, "version": new_ver, "ts": now})
        return {"ok": True, "version": new_ver}

    async def get(self, tenant: str, ns: str, resource_id: str) -> Optional[Dict[str, Any]]:
        """Return the current-state doc for one resource (or ``None``)."""
        return await self._db[STATE_COLLECTION].find_one(
            {"tenant": tenant, "ns": ns, "resource_id": str(resource_id)}, {"_id": 0, "tenant": 0})

    async def list(
        self, tenant: str, ns: str, filter: Optional[Dict[str, Any]] = None,
        limit: int = 200, skip: int = 0,
    ) -> List[Dict[str, Any]]:
        """List current-state docs in a namespace. ``filter`` may only constrain the
        app's own fields (``resource_id`` or ``data.*``); ``tenant`` is never overridable."""
        q: Dict[str, Any] = {"tenant": tenant, "ns": ns}
        for k, v in (filter or {}).items():
            if k == "tenant":
                continue
            q[k if (k == "resource_id" or k.startswith("data.")) else f"data.{k}"] = v
        cursor = self._db[STATE_COLLECTION].find(q, {"_id": 0, "tenant": 0}).skip(skip).limit(limit)
        return [d async for d in cursor]

    async def delete(self, tenant: str, ns: str, resource_id: str, event: bool = True) -> Dict[str, Any]:
        """Delete a resource's current state (history is retained)."""
        now = datetime.now(timezone.utc)
        key = {"tenant": tenant, "ns": ns, "resource_id": str(resource_id)}
        result = await self._db[STATE_COLLECTION].delete_one(key)
        if event and result.deleted_count:
            await self._db[EVENTS_COLLECTION].insert_one({
                "_id": str(uuid.uuid4()), **key, "op": "delete",
                "patch": None, "version": None, "ts": now})
        return {"ok": True, "deleted": result.deleted_count}

    async def history(
        self, tenant: str, ns: str, resource_id: Optional[str] = None,
        limit: int = 100, skip: int = 0,
    ) -> List[Dict[str, Any]]:
        """Return the append-only activity log (newest first), optionally for one resource."""
        q: Dict[str, Any] = {"tenant": tenant, "ns": ns}
        if resource_id is not None:
            q["resource_id"] = str(resource_id)
        cursor = self._db[EVENTS_COLLECTION].find(q, {"_id": 0, "tenant": 0}).sort("ts", -1).skip(skip).limit(limit)
        return [d async for d in cursor]


def tenant_key(account_id: Optional[str] = None, user_id: Optional[str] = None,
               session_id: Optional[str] = None) -> str:
    """Build the document isolation key from token claims (session > account > user)."""
    if session_id:
        return "session:" + re.sub(r"[^a-zA-Z0-9]", "_", session_id)
    if account_id:
        return "account:" + re.sub(r"[^a-zA-Z0-9]", "_", account_id)
    return "user:" + re.sub(r"[^a-zA-Z0-9]", "_", user_id or "_unknown")
