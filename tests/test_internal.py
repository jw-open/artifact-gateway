"""Tests for artifact_gateway.internal.InternalProxy."""
from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from artifact_gateway.internal import DEFAULT_ALLOWLIST, InternalProxy

BASE_URL = "http://localhost:8000"
USER_JWT = "eyJ.fake.jwt"

READ_SCOPE = ["internal:read"]
WRITE_SCOPE = ["internal:read", "internal:write"]
NO_SCOPE: list = []


@pytest.fixture()
def proxy() -> InternalProxy:
    return InternalProxy(base_url=BASE_URL)


# --- allowlist checks ---

async def test_path_not_in_allowlist_raises_permission_error(proxy: InternalProxy):
    with pytest.raises(PermissionError, match="allowlist"):
        await proxy.call(
            scope=READ_SCOPE,
            user_jwt=USER_JWT,
            path="/api/secret/admin",
            method="GET",
        )


async def test_method_not_allowed_for_path_raises_permission_error(proxy: InternalProxy):
    # /api/knowledge only allows GET
    with pytest.raises(PermissionError, match="not allowed"):
        await proxy.call(
            scope=WRITE_SCOPE,
            user_jwt=USER_JWT,
            path="/api/knowledge/graphs",
            method="POST",
        )


# --- scope checks ---

async def test_write_method_requires_internal_write_scope(proxy: InternalProxy):
    with pytest.raises(PermissionError, match="internal:write"):
        await proxy.call(
            scope=READ_SCOPE,
            user_jwt=USER_JWT,
            path="/api/agent",
            method="POST",
        )


async def test_no_scope_raises_permission_error_for_get(proxy: InternalProxy):
    with pytest.raises(PermissionError, match="internal:read"):
        await proxy.call(
            scope=NO_SCOPE,
            user_jwt=USER_JWT,
            path="/api/agent",
            method="GET",
        )


async def test_read_scope_allows_get(proxy: InternalProxy, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE_URL}/api/agent",
        json={"agents": []},
        status_code=200,
    )
    result = await proxy.call(
        scope=READ_SCOPE,
        user_jwt=USER_JWT,
        path="/api/agent",
        method="GET",
    )
    assert result["status"] == 200
    assert result["body"] == {"agents": []}


async def test_write_scope_allows_post(proxy: InternalProxy, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE_URL}/api/agent",
        json={"id": "new-agent"},
        status_code=201,
    )
    result = await proxy.call(
        scope=WRITE_SCOPE,
        user_jwt=USER_JWT,
        path="/api/agent",
        method="POST",
        body={"name": "test"},
    )
    assert result["status"] == 201


# --- JWT forwarding ---

async def test_user_jwt_forwarded_as_authorization_header(
    proxy: InternalProxy, httpx_mock: HTTPXMock
):
    captured_headers: dict = {}

    def capture_request(request: object) -> None:
        import httpx as _httpx
        captured_headers.update(dict(request.headers))  # type: ignore[attr-defined]

    httpx_mock.add_response(
        method="GET",
        url=f"{BASE_URL}/api/agent",
        json={},
        status_code=200,
    )
    await proxy.call(
        scope=READ_SCOPE,
        user_jwt=USER_JWT,
        path="/api/agent",
        method="GET",
    )
    # Retrieve the actual request that was sent.
    requests = httpx_mock.get_requests()
    assert len(requests) == 1
    assert requests[0].headers["authorization"] == f"Bearer {USER_JWT}"


# --- response handling ---

async def test_non_json_response_returns_text(proxy: InternalProxy, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE_URL}/api/studio",
        text="plain text",
        headers={"content-type": "text/plain"},
        status_code=200,
    )
    result = await proxy.call(
        scope=READ_SCOPE,
        user_jwt=USER_JWT,
        path="/api/studio",
        method="GET",
    )
    assert result["body"] == "plain text"


async def test_query_params_forwarded(proxy: InternalProxy, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE_URL}/api/agent?limit=10",
        json={"agents": []},
        status_code=200,
    )
    result = await proxy.call(
        scope=READ_SCOPE,
        user_jwt=USER_JWT,
        path="/api/agent",
        method="GET",
        query={"limit": "10"},
    )
    assert result["status"] == 200


# --- custom allowlist ---

async def test_custom_allowlist_respected():
    custom_proxy = InternalProxy(
        base_url=BASE_URL,
        allowlist=[("/api/custom", ["GET"])],
    )
    with pytest.raises(PermissionError, match="allowlist"):
        await custom_proxy.call(
            scope=READ_SCOPE,
            user_jwt=USER_JWT,
            path="/api/agent",
            method="GET",
        )


async def test_default_allowlist_exported():
    assert isinstance(DEFAULT_ALLOWLIST, list)
    assert len(DEFAULT_ALLOWLIST) > 0
    for item in DEFAULT_ALLOWLIST:
        assert isinstance(item, tuple)
        assert len(item) == 2
