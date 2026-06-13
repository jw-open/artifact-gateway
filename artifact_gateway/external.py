"""External HTTPS API proxy — CORS bypass for iframe artifact apps."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

MAX_BODY_BYTES: int = 4 * 1024 * 1024  # 4 MB
DEFAULT_TIMEOUT: float = 30.0


class ExternalProxy:
    """Proxy HTTP calls from artifact apps to external HTTPS APIs.

    Only allowed when token scope contains ``'external:*'``.
    Only HTTPS URLs are accepted to prevent SSRF to internal services.
    Request/response bodies are capped at MAX_BODY_BYTES.
    The user's OhWise JWT is never forwarded to external targets.
    """

    def __init__(
        self,
        timeout: float = DEFAULT_TIMEOUT,
        max_body_bytes: int = MAX_BODY_BYTES,
    ) -> None:
        """Initialise the proxy.

        Args:
            timeout: HTTP request timeout in seconds.
            max_body_bytes: Maximum response body size in bytes.
        """
        self.timeout = timeout
        self.max_body_bytes = max_body_bytes

    def _require_scope(self, scope: List[str]) -> None:
        """Raise PermissionError if ``external:*`` is absent from scope."""
        if "external:*" not in scope:
            raise PermissionError(
                "Scope 'external:*' is required for external proxy calls"
            )

    async def call(
        self,
        *,
        scope: List[str],
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        body: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Proxy an HTTP call to an external HTTPS API.

        Args:
            scope: Token scope claims from the validated app token.
            method: HTTP method (GET, POST, PUT, PATCH, DELETE).
            url: Target HTTPS URL. Must begin with ``https://``.
            headers: Optional headers to forward. The user's OhWise JWT is
                never forwarded regardless of what is passed here.
            body: Optional JSON-serialisable request body.

        Returns:
            ``{"status": int, "headers": dict, "body": any}``

        Raises:
            PermissionError: If scope is insufficient or the URL is not HTTPS.
            httpx.HTTPError: On network-level failure.
        """
        self._require_scope(scope)
        if not url.startswith("https://"):
            raise PermissionError(
                "Only HTTPS URLs are permitted for external proxy calls"
            )

        logger.debug("ExternalProxy: %s %s", method.upper(), url)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(
                method=method.upper(),
                url=url,
                headers=headers or {},
                json=body,
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
            "headers": dict(response.headers),
            "body": body_out,
        }
