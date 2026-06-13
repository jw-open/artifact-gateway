"""DuckDB handler — per-user and per-session isolated DuckDB file access."""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Scope constants used to select the correct DB path.
SCOPE_USER = "user"
SCOPE_SESSION = "session"


class DuckDBHandler:
    """Manage user-isolated DuckDB database files.

    Each user (or session) gets their own DuckDB file on the local filesystem.
    Connections are cached per file path and protected by per-file asyncio locks
    to prevent concurrent write corruption.

    DuckDB is an optional dependency.  Import is deferred to method bodies so
    the base ``artifact-gateway`` package works without it installed.

    File layout::

        {workspace}/{user_id}/db/{name}.duckdb                           # user scope
        {workspace}/{user_id}/sessions/{session_id}/db/{name}.duckdb    # session scope
    """

    def __init__(self, workspace: str) -> None:
        """Initialise the handler.

        Args:
            workspace: Root directory for all user workspaces
                (i.e. ``LAB_WORKSPACE_ROOT``).
        """
        self.workspace = workspace
        self._connections: Dict[str, Any] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

    def _db_path(
        self,
        scope: str,
        user_id: str,
        db_name: str,
        session_id: Optional[str] = None,
    ) -> Path:
        """Compute the filesystem path for a DuckDB file.

        Args:
            scope: ``"user"`` or ``"session"``.
            user_id: User identifier (from token claims).
            db_name: Logical database name (filename without extension).
            session_id: Required when ``scope="session"``.

        Returns:
            Absolute :class:`pathlib.Path` to the ``.duckdb`` file.

        Raises:
            ValueError: If ``scope="session"`` but ``session_id`` is not provided.
        """
        if scope == SCOPE_SESSION:
            if not session_id:
                raise ValueError("session_id is required for session-scoped DuckDB")
            return (
                Path(self.workspace)
                / user_id
                / "sessions"
                / session_id
                / "db"
                / f"{db_name}.duckdb"
            )
        return Path(self.workspace) / user_id / "db" / f"{db_name}.duckdb"

    def _get_connection(self, db_path: Path) -> Any:
        """Return (and cache) a DuckDB connection for the given path.

        The parent directory is created if it does not exist.

        Args:
            db_path: Absolute path to the ``.duckdb`` file.

        Returns:
            An open ``duckdb.DuckDBPyConnection`` instance.
        """
        try:
            import duckdb  # noqa: PLC0415 — lazy import
        except ImportError as exc:
            raise ImportError(
                "duckdb is required for DuckDBHandler. "
                "Install it with: pip install 'artifact-gateway[duckdb]'"
            ) from exc

        key = str(db_path)
        if key not in self._connections:
            db_path.parent.mkdir(parents=True, exist_ok=True)
            logger.debug("DuckDBHandler: opening %s", key)
            self._connections[key] = duckdb.connect(str(db_path))
        return self._connections[key]

    def _get_lock(self, db_path: Path) -> asyncio.Lock:
        """Return (and cache) an asyncio.Lock for the given DuckDB file."""
        key = str(db_path)
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]

    async def query(
        self,
        scope: str,
        user_id: str,
        db_name: str,
        sql: str,
        params: Optional[List[Any]] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a SELECT query and return results.

        Runs the blocking DuckDB call in the default asyncio thread-pool
        executor so the event loop is not blocked.

        Args:
            scope: ``"user"`` or ``"session"``.
            user_id: User identifier (from token claims).
            db_name: Logical database name.
            sql: SQL SELECT statement.
            params: Optional positional parameters.
            session_id: Required when ``scope="session"``.

        Returns:
            ``{"columns": [...], "rows": [[...], ...], "rowcount": N}``
        """
        db_path = self._db_path(scope, user_id, db_name, session_id)
        lock = self._get_lock(db_path)

        def _run() -> Dict[str, Any]:
            conn = self._get_connection(db_path)
            result = conn.execute(sql, params or [])
            columns = [desc[0] for desc in result.description or []]
            rows = result.fetchall()
            return {
                "columns": columns,
                "rows": [list(row) for row in rows],
                "rowcount": len(rows),
            }

        async with lock:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, _run)

    async def exec(
        self,
        scope: str,
        user_id: str,
        db_name: str,
        sql: str,
        params: Optional[List[Any]] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a non-SELECT statement (CREATE, INSERT, UPDATE, DELETE).

        Args:
            scope: ``"user"`` or ``"session"``.
            user_id: User identifier (from token claims).
            db_name: Logical database name.
            sql: SQL statement to execute.
            params: Optional positional parameters.
            session_id: Required when ``scope="session"``.

        Returns:
            ``{"success": True}``
        """
        db_path = self._db_path(scope, user_id, db_name, session_id)
        lock = self._get_lock(db_path)

        def _run() -> None:
            conn = self._get_connection(db_path)
            conn.execute(sql, params or [])

        async with lock:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, _run)

        return {"success": True}
