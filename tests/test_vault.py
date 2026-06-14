"""Tests for artifact_gateway.vault."""
from __future__ import annotations

import pytest

from artifact_gateway.vault import (
    CredentialVault,
    apply_credential,
    PLACEMENT_BEARER,
    PLACEMENT_HEADER,
    PLACEMENT_QUERY,
)

MASTER = "master-key-for-testing-only"


def test_encrypt_decrypt_roundtrip():
    vault = CredentialVault(MASTER)
    secret = "super-secret-api-token-12345"
    token = vault.encrypt(secret)
    assert token != secret
    assert vault.decrypt(token) == secret


def test_encrypt_is_nondeterministic():
    vault = CredentialVault(MASTER)
    a = vault.encrypt("same")
    b = vault.encrypt("same")
    assert a != b  # random nonce per call
    assert vault.decrypt(a) == vault.decrypt(b) == "same"


def test_wrong_key_fails():
    token = CredentialVault(MASTER).encrypt("secret")
    with pytest.raises(ValueError, match="decryption failed"):
        CredentialVault("different-key").decrypt(token)


def test_tampered_ciphertext_fails():
    vault = CredentialVault(MASTER)
    token = vault.encrypt("secret")
    tampered = token[:-4] + ("AAAA" if token[-4:] != "AAAA" else "BBBB")
    with pytest.raises(ValueError):
        vault.decrypt(tampered)


def test_empty_master_key_rejected():
    with pytest.raises(ValueError):
        CredentialVault("")


def test_apply_credential_bearer():
    headers, query = apply_credential(secret="tok", placement=PLACEMENT_BEARER)
    assert headers["Authorization"] == "Bearer tok"
    assert query == {}


def test_apply_credential_header():
    headers, _ = apply_credential(
        secret="abc", placement=PLACEMENT_HEADER, name="X-Api-Key"
    )
    assert headers["X-Api-Key"] == "abc"


def test_apply_credential_query():
    _, query = apply_credential(
        secret="abc", placement=PLACEMENT_QUERY, name="api_key"
    )
    assert query["api_key"] == "abc"


def test_apply_credential_header_requires_name():
    with pytest.raises(ValueError):
        apply_credential(secret="x", placement=PLACEMENT_HEADER)


def test_apply_credential_unknown_placement():
    with pytest.raises(ValueError):
        apply_credential(secret="x", placement="nonsense")


def test_apply_credential_does_not_mutate_inputs():
    base_headers = {"Accept": "application/json"}
    headers, _ = apply_credential(
        secret="tok", placement=PLACEMENT_BEARER, headers=base_headers
    )
    assert "Authorization" in headers
    assert "Authorization" not in base_headers  # original untouched
