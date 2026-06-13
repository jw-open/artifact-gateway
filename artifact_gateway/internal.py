"""Internal OhWise API proxy — forwards calls with user JWT, enforces allowlist."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT: float = 30.0
WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# (path_prefix, allowed_methods) — configurable per deployment
DEFAULT_ALLOWLIST: List[Tuple[str, List[str]]] = [
    ("/api/agent", ["GET", "POST", "PUT", "DELETE"]),
    ("/api/knowledge", ["GET"]),
    ("/api/variable", ["GET"]),
    ("/api/studio", ["GET"]),
    ("/api/chat", ["GET", "POST"]),
]


class InternalProxy:
    """Proxy HTTP calls from artifact apps to internal OhWise APIs.

    Forwards the user's JWT so RBAC is enforced by the internal service.
    Path + method must appear in the configured allowlist.
    Paths not on the allowlist result in a 403-equivalent PermissionError.
    """

    def __init__(
        self,
        base_url: str,
        allowlist: Optional[List[Tuple[str, List[str]]]] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialise the proxy.

        Args:
            base_url: Base URL of the OhWise backend, e.g. ``http://localhost:8000``.
            allowlist: List of ``(path_prefix, allowed_methods)`` tuples.
                Defaults to :data:`DEFAULT_ALLOWLIST`.
            timeout: HTTP request timeout in seconds.
        """
        self.base_url = base_url.rstrip("/")
        self.allowlist = allowlist if allowlist is not None else DEFAULT_ALLOWLIST
        self.timeout = timeout

    def _check_allowlist(self, path: str, method: str) -> None:
        """Raise PermissionError if path+method is not on the allowlist."""
        method_upper = method.upper()
        for prefix, allowed_methods in self.allowlist:
            if path.startswith(prefix):
                if method_upper in [m.upper() for m in allowed_methods]:
                    return
                raise PermissionError(
                    f"Method {method_upper} is not allowed for internal path {path}"
                )
        raise PermissionError(
            f"Path '{path}' is not in the internal API allowlist"
        )

    def _require_scope(self, scope: List[str], method: str) -> None:
        """Raise PermissionError if the token scope is insufficient for the method."""
        if method.upper() in WRITE_METHODS:
            if "internal:write" not in scope:
                raise PermissionError(
                    "Scope 'internal:write' is required for mutating internal API calls"
                )
        else:
            if "internal:read" not in scope and "internal:write" not in scope:
                raise PermissionError(
                    "Scope 'internal:read' is required for internal API calls"
                )

    async def call(
        self,
        *,
        scope: List[str],
        user_jwt: str,
        path: str,
        method: str = "GET",
        body: Optional[Any] = None,
        query: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Proxy a call to an internal OhWise API endpoint.

        The user's JWT is forwarded verbatim so the target service can enforce
        its own RBAC rules without the proxy needing to replicate them.

        Args:
            scope: Token scope claims from the validated app token.
            user_jwt: The user's OhWise JWT (forwarded as ``Authorization: Bearer``).
            path: API path, must start with ``/api/``.
            method: HTTP method. Defaults to ``GET``.
            body: Optional JSON-serialisable body for POST/PUT/PATCH.
            query: Optional query string parameters.

        Returns:
            ``{"status": int, "body": any}``

        Raises:
            PermissionError: If scope insufficient or path/method not allowlisted.
            httpx.HTTPError: On network-level failure.
        """
        self._require_scope(scope, method)
        self._check_allowlist(path, method)

        url = f"{self.base_url}{path}"
        logger.debug("InternalProxy: %s %s", method.upper(), url)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(
                method=method.upper(),
                url=url,
                headers={"Authorization": f"Bearer {user_jwt}"},
                json=body,
                params=query,
            )

        content_type = response.headers.get("content-type", "")
        try:
            body_out: Any = (
                response.json()
                if "application/json" in content_type
                else response.text
            )
        except Exception:
            body_out = response.text

        return {
            "status": response.status_code,
            "body": body_out,
        }
