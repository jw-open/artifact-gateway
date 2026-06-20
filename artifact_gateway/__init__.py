"""artifact-gateway — Secure API gateway for AI-generated artifact apps."""
__version__ = "0.3.0"

from artifact_gateway.token import (
    issue_app_token,
    validate_app_token,
    refresh_app_token,
    scope_from_role,
)
from artifact_gateway.external import ExternalProxy
from artifact_gateway.internal import InternalProxy, DEFAULT_ALLOWLIST
from artifact_gateway.vault import (
    CredentialVault,
    apply_credential,
    PLACEMENT_BEARER,
    PLACEMENT_HEADER,
    PLACEMENT_QUERY,
)
from artifact_gateway.files import FilesHandler
from artifact_gateway.db.state import StateStore, VersionConflict, tenant_key
from artifact_gateway.models import (
    ExternalCallRequest,
    InternalCallRequest,
    DBQueryRequest,
    MongoFindRequest,
    MongoUpsertRequest,
    MongoDeleteRequest,
    AppTokenClaims,
    FileWriteRequest,
    FileReadRequest,
    FileListRequest,
    FileDeleteRequest,
)

__all__ = [
    "__version__",
    "issue_app_token",
    "validate_app_token",
    "refresh_app_token",
    "scope_from_role",
    "ExternalProxy",
    "InternalProxy",
    "DEFAULT_ALLOWLIST",
    "CredentialVault",
    "apply_credential",
    "PLACEMENT_BEARER",
    "PLACEMENT_HEADER",
    "PLACEMENT_QUERY",
    "FilesHandler",
    "StateStore",
    "VersionConflict",
    "tenant_key",
    "ExternalCallRequest",
    "InternalCallRequest",
    "DBQueryRequest",
    "MongoFindRequest",
    "MongoUpsertRequest",
    "MongoDeleteRequest",
    "AppTokenClaims",
    "FileWriteRequest",
    "FileReadRequest",
    "FileListRequest",
    "FileDeleteRequest",
]
