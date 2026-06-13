# Changelog

## [0.1.0] - 2026-06-13

### Added

- Initial release
- JWT-based app token issuance and validation (`issue_app_token`, `validate_app_token`, `scope_from_role`)
- Role-to-scope mapping for viewer / member / admin / system_admin / platform_owner
- External HTTPS API proxy (`ExternalProxy`) — CORS bypass for iframe artifact apps; enforces HTTPS-only, scope check, 4 MB body cap
- Internal OhWise API proxy with allowlist enforcement (`InternalProxy`) — forwards user JWT for downstream RBAC; configurable path+method allowlist
- User-isolated DuckDB handler (`DuckDBHandler`) — per-file connection cache, asyncio executor, user and session scope — optional, install with `artifact-gateway[duckdb]`
- User-isolated MongoDB handler (`MongoHandler`) — collection namespacing, async CRUD via Motor — optional, install with `artifact-gateway[mongo]`
- Pydantic v2 request/response models (`ExternalCallRequest`, `InternalCallRequest`, `DBQueryRequest`, `MongoFindRequest`, `MongoUpsertRequest`, `MongoDeleteRequest`, `AppTokenClaims`)
- Test suite with pytest-asyncio, pytest-httpx, and mongomock-motor
- GitHub Actions CI (Python 3.10 / 3.11 / 3.12) and PyPI publish workflow
