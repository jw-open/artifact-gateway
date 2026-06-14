"""Credential vault — AES-256-GCM encryption for named external credentials.

Artifact apps reference credentials by name (``credential_id``) instead of
embedding secrets in generated code. The gateway resolves the name to the real
secret at request time and injects it into the outbound request. Secrets are
stored encrypted at rest; only the vault (holding the master key) can decrypt.

The vault itself is storage-agnostic: it only encrypts and decrypts. The caller
is responsible for persisting the ciphertext (e.g. in MongoDB).
"""
from __future__ import annotations

import base64
import hashlib
import os
from typing import Any, Dict, Optional

# Where to place a resolved credential in the outbound request.
PLACEMENT_HEADER = "header"
PLACEMENT_QUERY = "query"
PLACEMENT_BEARER = "bearer"  # shorthand for Authorization: Bearer <secret>


class CredentialVault:
    """Encrypt and decrypt credential secrets with AES-256-GCM.

    The master key is hashed to a 32-byte key with SHA-256, so any string of
    any length is accepted. Each ``encrypt`` call uses a fresh random 96-bit
    nonce; the output is ``base64(nonce || ciphertext_with_tag)``.

    ``cryptography`` is a hard dependency of artifact-gateway, so no lazy import
    is needed here.
    """

    def __init__(self, master_key: str) -> None:
        """Initialise the vault.

        Args:
            master_key: Secret string used to derive the AES-256 key. Typically
                the service ``ENCRYPTION_KEY`` (falls back to ``SECRET_KEY``).
        """
        if not master_key:
            raise ValueError("CredentialVault requires a non-empty master_key")
        self._key = hashlib.sha256(master_key.encode("utf-8")).digest()

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a secret string, returning a base64-encoded token."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        nonce = os.urandom(12)
        aesgcm = AESGCM(self._key)
        ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return base64.b64encode(nonce + ct).decode("ascii")

    def decrypt(self, token: str) -> str:
        """Decrypt a base64 token produced by :meth:`encrypt`.

        Raises:
            ValueError: If the token is malformed or fails authentication.
        """
        from cryptography.exceptions import InvalidTag
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        try:
            raw = base64.b64decode(token)
        except Exception as exc:  # noqa: BLE001
            raise ValueError("Invalid credential ciphertext encoding") from exc
        if len(raw) < 13:
            raise ValueError("Credential ciphertext too short")
        nonce, ct = raw[:12], raw[12:]
        aesgcm = AESGCM(self._key)
        try:
            return aesgcm.decrypt(nonce, ct, None).decode("utf-8")
        except InvalidTag as exc:
            raise ValueError("Credential decryption failed (wrong key or tampered)") from exc


def apply_credential(
    *,
    secret: str,
    placement: str = PLACEMENT_BEARER,
    name: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    query: Optional[Dict[str, Any]] = None,
) -> tuple[Dict[str, str], Dict[str, Any]]:
    """Inject a resolved secret into request headers or query parameters.

    Args:
        secret: The decrypted credential value.
        placement: One of ``"bearer"`` (``Authorization: Bearer <secret>``),
            ``"header"`` (custom header named by ``name``), or ``"query"``
            (query parameter named by ``name``).
        name: Header or query-parameter name. Required for ``header``/``query``.
        headers: Existing headers dict to extend (copied, not mutated).
        query: Existing query dict to extend (copied, not mutated).

    Returns:
        ``(headers, query)`` — new dicts with the credential applied.

    Raises:
        ValueError: If ``placement`` is unknown or ``name`` is missing where
            required.
    """
    out_headers = dict(headers or {})
    out_query = dict(query or {})

    if placement == PLACEMENT_BEARER:
        out_headers["Authorization"] = f"Bearer {secret}"
    elif placement == PLACEMENT_HEADER:
        if not name:
            raise ValueError("placement 'header' requires a header name")
        out_headers[name] = secret
    elif placement == PLACEMENT_QUERY:
        if not name:
            raise ValueError("placement 'query' requires a query parameter name")
        out_query[name] = secret
    else:
        raise ValueError(f"Unknown credential placement: {placement}")

    return out_headers, out_query
