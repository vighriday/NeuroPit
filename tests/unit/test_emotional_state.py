"""Unit tests for the emotional state engine."""

from __future__ import annotations

import math

from src.backend.inference.emotional_state import EMOTIONS, evaluate


def _state(**overrides) -> dict:
    base = {
        "driver_id": "VER",
        "timestamp": "2026-05-19T12:00:00Z",
        "stress_score": 40.0,
        "confidence_score": 70.0,
        "fatigue_score": 20.0,
        "cognitive_load_score": 30.0,
        "attention_stability": 65.0,
        "strategic_reliability": 60.0,
        "panic_probability": 10.0,
        "emotional_drift_score": 5.0,
        "tunnel_vision_prob": 0.0,
        "persona_state": "Recovery",
        "confidence_band": "moderate",
    }
    base.update(overrides)
    return base


def test_distribution_sums_to_one():
    report = evaluate(_state(), features={"throttle_commitment": 60.0}, biometrics={"synthetic_hrv": 50.0})
    total = sum(report.distribution.values())
    assert math.isclose(total, 1.0, abs_tol=1e-3)
    assert set(report.distribution.keys()) == set(EMOTIONS)


def test_panic_state_returns_panic_dominant():
    report = evaluate(
        _state(stress_score=92.0, panic_probability=85.0, persona_state="Panic", tunnel_vision_prob=100.0, confidence_score=20.0),
        features={"panic_oscillation": 30.0, "throttle_commitment": 40.0},
        biometrics={"synthetic_hrv": 18.0},
    )
    assert report.dominant_emotion in {"panic", "fear"}


def test_calm_state_returns_confidence_or_recovery():
    report = evaluate(
        _state(stress_score=15.0, confidence_score=92.0, persona_state="Flow State", cognitive_load_score=10.0),
        features={"throttle_commitment": 50.0, "panic_oscillation": 1.0, "braking_hesitation": 10.0},
        biometrics={"synthetic_hrv": 60.0},
    )
    assert report.dominant_emotion in {"confidence", "recovery"}


def test_radio_features_lift_frustration():
    quiet = evaluate(_state(), features={}, biometrics={"synthetic_hrv": 50.0})
    angry = evaluate(_state(), features={}, biometrics={"synthetic_hrv": 50.0}, radio_features={"anger_intensity": 0.95})
    assert angry.distribution["frustration"] >= quiet.distribution["frustration"]


def test_dominant_probability_within_unit_range():
    report = evaluate(_state(), features={"throttle_commitment": 60.0}, biometrics={})
    assert 0.0 <= report.dominant_probability <= 1.0
