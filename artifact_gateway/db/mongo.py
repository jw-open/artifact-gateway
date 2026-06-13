"""MongoDB handler — per-user and per-session isolated collection access."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Scope constants used to select the correct collection prefix.
SCOPE_USER = "user"
SCOPE_SESSION = "session"


class MongoHandler:
    """Manage user-isolated MongoDB collections via Motor (async).

    Collections are namespaced by user or session so that data from different
    users can never collide.  User code never sees the full MongoDB collection
    name — the proxy constructs it transparently.

    Collection naming::

        app_user_{user_id}_{collection}          # user scope
        app_session_{session_id}_{collection}    # session scope

    Motor is an optional dependency.  Pass the Motor ``AsyncIOMotorDatabase``
    object at construction time; the caller is responsible for creating it.
    """

    def __init__(self, db: Any) -> None:
        """Initialise the handler.

        Args:
            db: A Motor ``AsyncIOMotorDatabase`` instance.
        """
        self._db = db

    def _collection_name(
        self,
        scope: str,
        user_id: str,
        collection: str,
        session_id: Optional[str] = None,
    ) -> str:
        """Compute the namespaced MongoDB collection name.

        Args:
            scope: ``"user"`` or ``"session"``.
            user_id: User identifier (from token claims).
            collection: Logical collection name provided by the artifact app.
            session_id: Required when ``scope="session"``.

        Returns:
            Full collection name string.

        Raises:
            ValueError: If ``scope="session"`` but ``session_id`` is not provided.
        """
        if scope == SCOPE_SESSION:
            if not session_id:
                raise ValueError("session_id is required for session-scoped MongoDB")
            return f"app_session_{session_id}_{collection}"
        return f"app_user_{user_id}_{collection}"

    async def find(
        self,
        scope: str,
        user_id: str,
        collection: str,
        filter: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        session_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Find documents matching a filter.

        Args:
            scope: ``"user"`` or ``"session"``.
            user_id: User identifier (from token claims).
            collection: Logical collection name.
            filter: MongoDB query filter. Defaults to ``{}`` (all documents).
            limit: Maximum number of documents to return.
            session_id: Required when ``scope="session"``.

        Returns:
            List of document dicts (``_id`` serialised as string).
        """
        col_name = self._collection_name(scope, user_id, collection, session_id)
        col = self._db[col_name]
        query_filter = filter or {}
        logger.debug("MongoHandler.find: collection=%s filter=%s", col_name, query_filter)
        cursor = col.find(query_filter).limit(limit)
        docs = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            docs.append(doc)
        return docs

    async def upsert(
        self,
        scope: str,
        user_id: str,
        collection: str,
        filter: Dict[str, Any],
        update: Dict[str, Any],
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Upsert a document matching the filter.

        Args:
            scope: ``"user"`` or ``"session"``.
            user_id: User identifier (from token claims).
            collection: Logical collection name.
            filter: MongoDB filter to match the target document.
            update: MongoDB update document (operators or replacement).
            session_id: Required when ``scope="session"``.

        Returns:
            ``{"matched": N, "modified": N, "upserted": bool}``
        """
        col_name = self._collection_name(scope, user_id, collection, session_id)
        col = self._db[col_name]
        logger.debug("MongoHandler.upsert: collection=%s filter=%s", col_name, filter)
        result = await col.update_one(filter, update, upsert=True)
        return {
            "matched": result.matched_count,
            "modified": result.modified_count,
            "upserted": result.upserted_id is not None,
        }

    async def delete(
        self,
        scope: str,
        user_id: str,
        collection: str,
        filter: Dict[str, Any],
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Delete documents matching a filter.

        Args:
            scope: ``"user"`` or ``"session"``.
            user_id: User identifier (from token claims).
            collection: Logical collection name.
            filter: MongoDB filter to match documents to delete.
            session_id: Required when ``scope="session"``.

        Returns:
            ``{"deleted": N}``
        """
        col_name = self._collection_name(scope, user_id, collection, session_id)
        col = self._db[col_name]
        logger.debug("MongoHandler.delete: collection=%s filter=%s", col_name, filter)
        result = await col.delete_many(filter)
        return {"deleted": result.deleted_count}
