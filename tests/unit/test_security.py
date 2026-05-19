"""Unit tests for the security helpers (tokens, roles, crypto)."""

from __future__ import annotations

import time

import pytest

from src.backend.config import get_settings
from src.backend.security import crypto, roles, tokens


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch):
    monkeypatch.setenv("API_JWT_SECRET", "unit-test-secret-key")
    monkeypatch.setenv("API_JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("ENCRYPTION_KEY", "")
    monkeypatch.setenv("BIOMETRIC_RETENTION_HOURS", "1")
    get_settings.cache_clear()  # type: ignore[attr-defined]
    yield
    get_settings.cache_clear()  # type: ignore[attr-defined]


def test_token_round_trip():
    token = tokens.issue_token("operator-1", "race_strategist", expires_in_seconds=60)
    claims = tokens.verify_token(token)
    assert claims.subject == "operator-1"
    assert claims.role == "race_strategist"
    assert claims.expires_at > claims.issued_at


def test_token_tampered_payload_fails():
    token = tokens.issue_token("operator-2", "team_principal", expires_in_seconds=60)
    with pytest.raises(ValueError):
        tokens.verify_token(token + "x")


def test_roles_listing_contains_documented_principals():
    names = {role.name for role in roles.list_roles()}
    assert {"team_principal", "race_strategist", "driver_engineer", "neuro_analyst"}.issubset(names)


def test_roles_scope_check():
    assert roles.has_scope("team_principal", "write:strategy_override")
    assert not roles.has_scope("driver_engineer", "write:strategy_override")
    assert not roles.has_scope("nonexistent", "read:cognitive")


def test_crypto_round_trip():
    encrypted = crypto.encrypt("driver-hr-178bpm")
    assert encrypted != "driver-hr-178bpm"
    assert crypto.decrypt(encrypted) == "driver-hr-178bpm"


def test_crypto_rejects_garbled_ciphertext():
    with pytest.raises(ValueError):
        crypto.decrypt("not-a-real-token")


def test_retention_window():
    assert crypto.is_expired(time.time() - 4000, retention_hours=1)
    assert not crypto.is_expired(time.time(), retention_hours=1)
