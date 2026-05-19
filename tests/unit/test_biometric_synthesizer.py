"""Unit tests for the biometric synthesiser.

We only exercise the deterministic synthesise method. The Kafka loop is
covered by the integration suite. Critically, we assert that every payload
carries an encrypted blob in addition to the plaintext numeric fields, so
the at rest encryption requirement from PRD section thirty four is honoured
at the source.
"""

from __future__ import annotations

import json

from src.backend.config import get_settings
from src.backend.inference.biometric_synthesizer import BiometricSynthesizer
from src.backend.security.crypto import decrypt


def _synth(monkeypatch) -> BiometricSynthesizer:
    monkeypatch.setenv("ENCRYPTION_KEY", "")
    get_settings.cache_clear()  # type: ignore[attr-defined]
    synth = BiometricSynthesizer.__new__(BiometricSynthesizer)
    synth.driver_state = {}
    return synth


def test_synthesize_returns_synthetic_label(monkeypatch):
    synth = _synth(monkeypatch)
    payload = synth.synthesize(
        "VER",
        {
            "timestamp": "2026-05-19T12:00:00Z",
            "features": {
                "steering_instability": 1.0,
                "throttle_commitment": 10.0,
                "panic_oscillation": 2.0,
            },
        },
    )
    assert payload["source"] == "synthetic"
    assert payload["driver_id"] == "VER"
    assert 110.0 <= payload["synthetic_hr"] <= 195.0
    assert 15.0 <= payload["synthetic_hrv"] <= 80.0
    get_settings.cache_clear()  # type: ignore[attr-defined]


def test_synthesize_encrypts_payload(monkeypatch):
    synth = _synth(monkeypatch)
    payload = synth.synthesize(
        "HAM",
        {
            "timestamp": "2026-05-19T12:00:00Z",
            "features": {"steering_instability": 2.0, "throttle_commitment": 30.0, "panic_oscillation": 5.0},
        },
    )
    assert payload["encrypted_payload"] != ""
    decrypted = json.loads(decrypt(payload["encrypted_payload"]))
    assert decrypted["synthetic_hr"] == payload["synthetic_hr"]
    assert decrypted["synthetic_hrv"] == payload["synthetic_hrv"]
    get_settings.cache_clear()  # type: ignore[attr-defined]
