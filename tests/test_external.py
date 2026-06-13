"""Tests for artifact_gateway.external.ExternalProxy."""
from __future__ import annotations

import pytest
import httpx
from pytest_httpx import HTTPXMock

from artifact_gateway.external import ExternalProxy

FULL_SCOPE = ["external:*", "internal:read"]
LIMITED_SCOPE = ["internal:read"]

URL = "https://api.example.com/v1/data"


@pytest.fixture()
def proxy() -> ExternalProxy:
    return ExternalProxy(timeout=5.0)


# --- scope checks ---

async def test_missing_scope_raises_permission_error(proxy: ExternalProxy):
    with pytest.raises(PermissionError, match="external:\\*"):
        await proxy.call(scope=LIMITED_SCOPE, method="GET", url=URL)


async def test_http_url_raises_permission_error(proxy: ExternalProxy):
    with pytest.raises(PermissionError, match="HTTPS"):
        await proxy.call(scope=FULL_SCOPE, method="GET", url="http://evil.com/steal")


# --- successful calls ---

async def test_successful_get_returns_status_headers_body(
    proxy: ExternalProxy, httpx_mock: HTTPXMock
):
    httpx_mock.add_response(
        method="GET",
        url=URL,
        json={"result": "ok"},
        status_code=200,
    )
    result = await proxy.call(scope=FULL_SCOPE, method="GET", url=URL)
    assert result["status"] == 200
    assert isinstance(result["headers"], dict)
    assert result["body"] == {"result": "ok"}


async def test_json_response_is_parsed(proxy: ExternalProxy, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=URL,
        json={"items": [1, 2, 3]},
        status_code=200,
    )
    result = await proxy.call(scope=FULL_SCOPE, method="GET", url=URL)
    assert isinstance(result["body"], dict)
    assert result["body"]["items"] == [1, 2, 3]


async def test_non_json_response_returns_text(proxy: ExternalProxy, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=URL,
        text="plain text response",
        headers={"content-type": "text/plain"},
        status_code=200,
    )
    result = await proxy.call(scope=FULL_SCOPE, method="GET", url=URL)
    assert result["body"] == "plain text response"


async def test_post_with_body(proxy: ExternalProxy, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="POST",
        url=URL,
        json={"created": True},
        status_code=201,
    )
    result = await proxy.call(
        scope=FULL_SCOPE,
        method="POST",
        url=URL,
        body={"name": "test"},
    )
    assert result["status"] == 201
    assert result["body"]["created"] is True


async def test_custom_headers_forwarded(proxy: ExternalProxy, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        method="GET",
        url=URL,
        json={},
        status_code=200,
    )
    # Should not raise — headers are accepted and forwarded.
    result = await proxy.call(
        scope=FULL_SCOPE,
        method="GET",
        url=URL,
        headers={"X-Api-Key": "secret-key"},
    )
    assert result["status"] == 200


async def test_4xx_response_returned_not_raised(proxy: ExternalProxy, httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=URL,
        json={"error": "not found"},
        status_code=404,
    )
    result = await proxy.call(scope=FULL_SCOPE, method="GET", url=URL)
    assert result["status"] == 404
    assert result["body"]["error"] == "not found"
