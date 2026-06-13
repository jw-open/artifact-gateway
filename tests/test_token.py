"""Tests for artifact_gateway.token."""
from __future__ import annotations

import time

import jwt
import pytest

from artifact_gateway.token import (
    DEFAULT_TTL,
    SCOPE_BY_ROLE,
    issue_app_token,
    scope_from_role,
    validate_app_token,
)

SECRET_KEY = "test-secret-key-for-testing-only"
USER_ID = "user-abc123"
ACCOUNT_ID = "account-xyz789"
CONTEXT = "lab_session:sess-001"
SCOPE = ["internal:read", "external:*"]


def test_issue_app_token_returns_string():
    token = issue_app_token(SECRET_KEY, USER_ID, ACCOUNT_ID, CONTEXT, SCOPE)
    assert isinstance(token, str)
    assert len(token) > 20


def test_validate_app_token_returns_correct_claims():
    token = issue_app_token(SECRET_KEY, USER_ID, ACCOUNT_ID, CONTEXT, SCOPE)
    claims = validate_app_token(SECRET_KEY, token)
    assert claims["user_id"] == USER_ID
    assert claims["account_id"] == ACCOUNT_ID
    assert claims["context"] == CONTEXT
    assert claims["scope"] == SCOPE
    assert "iat" in claims
    assert "exp" in claims


def test_validate_app_token_exp_is_in_future():
    token = issue_app_token(SECRET_KEY, USER_ID, ACCOUNT_ID, CONTEXT, SCOPE)
    claims = validate_app_token(SECRET_KEY, token)
    assert claims["exp"] > int(time.time())


def test_validate_app_token_custom_ttl():
    token = issue_app_token(SECRET_KEY, USER_ID, ACCOUNT_ID, CONTEXT, SCOPE, ttl=3600)
    claims = validate_app_token(SECRET_KEY, token)
    remaining = claims["exp"] - int(time.time())
    assert 3500 < remaining <= 3600


def test_expired_token_raises_value_error():
    now = int(time.time())
    payload = {
        "user_id": USER_ID,
        "account_id": ACCOUNT_ID,
        "context": CONTEXT,
        "scope": SCOPE,
        "iat": now - 7200,
        "exp": now - 3600,
    }
    expired_token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    with pytest.raises(ValueError, match="expired"):
        validate_app_token(SECRET_KEY, expired_token)


def test_tampered_token_raises_value_error():
    token = issue_app_token(SECRET_KEY, USER_ID, ACCOUNT_ID, CONTEXT, SCOPE)
    tampered = token[:-5] + "XXXXX"
    with pytest.raises(ValueError, match="Invalid app token"):
        validate_app_token(SECRET_KEY, tampered)


def test_wrong_secret_raises_value_error():
    token = issue_app_token(SECRET_KEY, USER_ID, ACCOUNT_ID, CONTEXT, SCOPE)
    with pytest.raises(ValueError, match="Invalid app token"):
        validate_app_token("wrong-secret", token)


# --- scope_from_role ---

def test_scope_from_role_viewer():
    scope = scope_from_role("viewer")
    assert "internal:read" in scope
    assert "external:*" not in scope
    assert "internal:write" not in scope
    assert "db:user:read" in scope


def test_scope_from_role_member():
    scope = scope_from_role("member")
    assert "external:*" in scope
    assert "internal:read" in scope
    assert "internal:write" in scope
    assert "db:user:rw" in scope
    assert "db:session:rw" in scope
    assert "db:shared:read" not in scope


def test_scope_from_role_admin():
    scope = scope_from_role("admin")
    assert "external:*" in scope
    assert "db:shared:read" in scope


def test_scope_from_role_system_admin():
    scope = scope_from_role("system_admin")
    assert "external:*" in scope
    assert "db:shared:read" in scope
    assert "internal:write" in scope


def test_scope_from_role_platform_owner():
    scope = scope_from_role("platform_owner")
    assert "external:*" in scope
    assert "db:shared:read" in scope
    assert "internal:write" in scope


def test_scope_from_role_unknown_defaults_to_viewer():
    scope = scope_from_role("nonexistent_role")
    viewer_scope = scope_from_role("viewer")
    assert scope == viewer_scope


def test_scope_from_role_returns_list():
    for role in SCOPE_BY_ROLE:
        assert isinstance(scope_from_role(role), list)


def test_scope_from_role_returns_copy():
    # Mutating the returned list must not affect the original mapping.
    scope = scope_from_role("viewer")
    original_len = len(scope)
    scope.append("hacked:scope")
    assert len(scope_from_role("viewer")) == original_len
