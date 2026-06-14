"""Files handler — user/session-isolated file read/write for artifact apps.

Artifacts can persist generated output (CSV exports, edited documents, rendered
files) back into the workspace, and read it back later. All paths are confined
to the owning user's (or session's) directory; traversal outside it is rejected.

File layout::

    {root}/{user_id}/files/{rel_path}                          # user scope
    {root}/{user_id}/sessions/{session_id}/{rel_path}          # session scope

Session-scope files are written into the session working directory so they are
immediately served by the existing session file-preview route.
"""
from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SCOPE_USER = "user"
SCOPE_SESSION = "session"

# Maximum single-file write size (8 MB).
DEFAULT_MAX_FILE_BYTES = 8 * 1024 * 1024


class FilesHandler:
    """Read, write, list, and delete files within an isolated workspace root."""

    def __init__(self, root: str, max_file_bytes: int = DEFAULT_MAX_FILE_BYTES) -> None:
        """Initialise the handler.

        Args:
            root: Workspace root (i.e. ``LAB_WORKSPACE_ROOT``).
            max_file_bytes: Maximum size of a single written file.
        """
        self.root = root
        self.max_file_bytes = max_file_bytes

    def _base_dir(
        self,
        scope: str,
        user_id: str,
        session_id: Optional[str] = None,
    ) -> Path:
        """Return the confinement root for the given scope."""
        safe_uid = _safe_segment(user_id)
        if scope == SCOPE_SESSION:
            if not session_id:
                raise ValueError("session_id is required for session-scoped files")
            return Path(self.root) / safe_uid / "sessions" / _safe_segment(session_id)
        return Path(self.root) / safe_uid / "files"

    def _resolve(
        self,
        scope: str,
        user_id: str,
        rel_path: str,
        session_id: Optional[str] = None,
    ) -> Path:
        """Resolve ``rel_path`` inside the scope's base dir, rejecting traversal.

        Raises:
            ValueError: If the resolved path escapes the confinement root.
        """
        base = self._base_dir(scope, user_id, session_id).resolve()
        candidate = (base / rel_path.lstrip("/")).resolve()
        if base != candidate and base not in candidate.parents:
            raise ValueError("Path escapes the workspace boundary")
        return candidate

    async def write(
        self,
        scope: str,
        user_id: str,
        rel_path: str,
        content: str,
        session_id: Optional[str] = None,
        encoding: str = "utf-8",
    ) -> Dict[str, Any]:
        """Write ``content`` to ``rel_path``. Parent dirs are created.

        Returns:
            ``{"path": str, "bytes": int}``
        """
        data = content.encode(encoding)
        if len(data) > self.max_file_bytes:
            raise ValueError(
                f"File exceeds max size ({len(data)} > {self.max_file_bytes} bytes)"
            )
        target = self._resolve(scope, user_id, rel_path, session_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        logger.debug("FilesHandler.write: %s (%d bytes)", target, len(data))
        return {"path": rel_path, "bytes": len(data)}

    async def read(
        self,
        scope: str,
        user_id: str,
        rel_path: str,
        session_id: Optional[str] = None,
        encoding: str = "utf-8",
    ) -> Dict[str, Any]:
        """Read a text file. Returns ``{"path": str, "content": str}``."""
        target = self._resolve(scope, user_id, rel_path, session_id)
        if not target.is_file():
            raise FileNotFoundError(rel_path)
        return {"path": rel_path, "content": target.read_text(encoding=encoding)}

    async def list(
        self,
        scope: str,
        user_id: str,
        rel_path: str = "",
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List entries under ``rel_path``. Returns ``{"entries": [...]}``."""
        target = self._resolve(scope, user_id, rel_path, session_id)
        if not target.exists():
            return {"entries": []}
        entries: List[Dict[str, Any]] = []
        for child in sorted(target.iterdir()):
            entries.append(
                {
                    "name": child.name,
                    "is_dir": child.is_dir(),
                    "bytes": child.stat().st_size if child.is_file() else None,
                }
            )
        return {"entries": entries}

    async def delete(
        self,
        scope: str,
        user_id: str,
        rel_path: str,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Delete a file or directory tree. Returns ``{"deleted": bool}``."""
        target = self._resolve(scope, user_id, rel_path, session_id)
        if not target.exists():
            return {"deleted": False}
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        return {"deleted": True}


def _safe_segment(value: str) -> str:
    """Sanitise a single path segment (user_id / session_id)."""
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in value)[:128]
