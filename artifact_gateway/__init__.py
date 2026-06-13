"""artifact-gateway — Secure API gateway for AI-generated artifact apps."""
__version__ = "0.1.0"

from artifact_gateway.token import issue_app_token, validate_app_token, scope_from_role
from artifact_gateway.external import ExternalProxy
from artifact_gateway.internal import InternalProxy, DEFAULT_ALLOWLIST
from artifact_gateway.models import (
    ExternalCallRequest,
    InternalCallRequest,
    DBQueryRequest,
    MongoFindRequest,
    MongoUpsertRequest,
    MongoDeleteRequest,
    AppTokenClaims,
)

__all__ = [
    "__version__",
    "issue_app_token",
    "validate_app_token",
    "scope_from_role",
    "ExternalProxy",
    "InternalProxy",
    "DEFAULT_ALLOWLIST",
    "ExternalCallRequest",
    "InternalCallRequest",
    "DBQueryRequest",
    "MongoFindRequest",
    "MongoUpsertRequest",
    "MongoDeleteRequest",
    "AppTokenClaims",
]
