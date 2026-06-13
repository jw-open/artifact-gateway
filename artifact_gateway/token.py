"""App token issuance and validation."""
from __future__ import annotations

import time
from typing import List

import jwt

DEFAULT_TTL = 14400  # 4 hours

SCOPE_BY_ROLE: dict[str, List[str]] = {
    "viewer": [
        "internal:read",
        "db:user:read",
        "db:session:read",
    ],
    "member": [
        "internal:read",
        "internal:write",
        "external:*",
        "db:user:read",
        "db:user:rw",
        "db:session:read",
        "db:session:rw",
    ],
    "admin": [
        "internal:read",
        "internal:write",
        "external:*",
        "db:user:read",
        "db:user:rw",
        "db:session:read",
        "db:session:rw",
        "db:shared:read",
    ],
    "system_admin": [
        "internal:read",
        "internal:write",
        "external:*",
        "db:user:read",
        "db:user:rw",
        "db:session:read",
        "db:session:rw",
        "db:shared:read",
    ],
    "platform_owner": [
        "internal:read",
        "internal:write",
        "external:*",
        "db:user:read",
        "db:user:rw",
        "db:session:read",
        "db:session:rw",
        "db:shared:read",
    ],
}


def issue_app_token(
    secret_key: str,
    user_id: str,
    account_id: str,
    context: str,
    scope: List[str],
    ttl: int = DEFAULT_TTL,
) -> str:
    """Issue a short-lived JWT app token scoped to user+context.

    Args:
        secret_key: HMAC-SHA256 signing secret (from service SECRET_KEY).
        user_id: The user's unique identifier.
        account_id: The account/tenant identifier.
        context: Scoping context string, e.g. ``lab_session:<session_id>``.
        scope: List of permission strings embedded into the token claims.
        ttl: Token lifetime in seconds. Defaults to 4 hours (14400).

    Returns:
        A signed JWT string.
    """
    now = int(time.time())
    payload = {
        "user_id": user_id,
        "account_id": account_id,
        "context": context,
        "scope": scope,
        "iat": now,
        "exp": now + ttl,
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")


def validate_app_token(secret_key: str, token: str) -> dict:
    """Validate an app token and return its claims.

    Args:
        secret_key: The same secret used when issuing the token.
        token: The JWT string to validate.

    Returns:
        Decoded claims dict.

    Raises:
        ValueError: If the token is expired or otherwise invalid.
    """
    try:
        return jwt.decode(token, secret_key, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise ValueError("App token has expired")
    except jwt.InvalidTokenError as exc:
        raise ValueError(f"Invalid app token: {exc}")


def scope_from_role(role: str) -> List[str]:
    """Derive app token scope list from a user's RBAC role string.

    Unknown roles fall back to the ``viewer`` scope (read-only).

    Args:
        role: RBAC role string (e.g. ``"member"``, ``"admin"``).

    Returns:
        List of scope strings for the given role.
    """
    return list(SCOPE_BY_ROLE.get(role, SCOPE_BY_ROLE["viewer"]))
