"""Pydantic v2 request/response models for artifact-gateway."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class ExternalCallRequest(BaseModel):
    """Request body for the external API proxy endpoint."""

    method: str = Field(..., description="HTTP method: GET, POST, PUT, PATCH, DELETE")
    url: str = Field(..., description="Target HTTPS URL")
    headers: Optional[Dict[str, str]] = Field(
        default=None, description="Headers to forward to the external API"
    )
    body: Optional[Any] = Field(
        default=None, description="JSON-serialisable request body"
    )

    @field_validator("method")
    @classmethod
    def validate_method(cls, v: str) -> str:
        allowed = {"GET", "POST", "PUT", "PATCH", "DELETE"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"method must be one of {allowed}")
        return upper

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError("url must start with https://")
        return v


class InternalCallRequest(BaseModel):
    """Request body for the internal OhWise API proxy endpoint."""

    method: str = Field(
        default="GET", description="HTTP method: GET, POST, PUT, PATCH, DELETE"
    )
    path: str = Field(
        ..., description="Internal API path starting with /api/"
    )
    body: Optional[Any] = Field(
        default=None, description="JSON-serialisable body for POST/PUT/PATCH"
    )
    query: Optional[Dict[str, str]] = Field(
        default=None, description="Query string parameters"
    )

    @field_validator("method")
    @classmethod
    def validate_method(cls, v: str) -> str:
        allowed = {"GET", "POST", "PUT", "PATCH", "DELETE"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"method must be one of {allowed}")
        return upper

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        if not v.startswith("/api/"):
            raise ValueError("path must start with /api/")
        return v


class DBQueryRequest(BaseModel):
    """Request body for DuckDB query and exec endpoints."""

    sql: str = Field(..., description="SQL statement to execute")
    params: Optional[List[Any]] = Field(
        default=None, description="Positional parameters for the SQL statement"
    )


class MongoFindRequest(BaseModel):
    """Request body for MongoDB find endpoint."""

    filter: Dict[str, Any] = Field(
        default_factory=dict, description="MongoDB query filter"
    )
    limit: int = Field(
        default=100, ge=1, le=10000, description="Maximum number of documents to return"
    )


class MongoUpsertRequest(BaseModel):
    """Request body for MongoDB upsert endpoint."""

    filter: Dict[str, Any] = Field(
        ..., description="Filter to match the document to upsert"
    )
    update: Dict[str, Any] = Field(
        ..., description="Update document (MongoDB update operators or replacement)"
    )


class MongoDeleteRequest(BaseModel):
    """Request body for MongoDB delete endpoint."""

    filter: Dict[str, Any] = Field(
        ..., description="Filter to match documents to delete"
    )


class AppTokenClaims(BaseModel):
    """Decoded claims from a validated app token."""

    user_id: str = Field(..., description="User unique identifier")
    account_id: str = Field(..., description="Account/tenant identifier")
    context: str = Field(
        ..., description="Scoping context, e.g. lab_session:<session_id>"
    )
    scope: List[str] = Field(..., description="Permission scope strings")
    iat: int = Field(..., description="Issued-at Unix timestamp")
    exp: int = Field(..., description="Expiry Unix timestamp")
