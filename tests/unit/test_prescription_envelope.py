"""Unit tests for the Driver Performance Envelope."""

from __future__ import annotations

import pytest

from src.backend.prescription.envelope import (
    COGNITIVE_DIMENSIONS,
    DriverPerformanceEnvelope,
    PERSONA_PRIORS,
)


def _state(persona: str = "Flow State", **overrides):
    base = {
        "driver_id": "VER",
        "stress_score": 28.0,
        "confidence_score": 84.0,
        "fatigue_score": 24.0,
        "cognitive_load_score": 38.0,
        "panic_probability": 4.0,
        "persona_state": persona,
        "confidence_band": "high",
    }
    base.update(overrides)
    return base


def test_envelope_bootstraps_from_persona_prior():
    env = DriverPerformanceEnvelope()
    centroid = env.ensure("VER", "Flow State")
    expected = PERSONA_PRIORS["Flow State"]
    for dim in COGNITIVE_DIMENSIONS:
        assert centroid.means[dim] == pytest.approx(expected[dim][0])
        assert centroid.tolerances[dim] >= 6.0


def test_envelope_invalid_smoothing_rejected():
    with pytest.raises(ValueError):
        DriverPerformanceEnvelope(smoothing=0.0)
    with pytest.raises(ValueError):
        DriverPerformanceEnvelope(smoothing=1.0)


def test_envelope_project_zero_distance_on_prior():
    env = DriverPerformanceEnvelope()
    projection = env.project("VER", _state())
    assert projection.weighted_distance == pytest.approx(0.0, abs=0.001)
    for dim in COGNITIVE_DIMENSIONS:
        assert projection.deltas[dim] == pytest.approx(0.0, abs=0.001)


def test_envelope_observe_moves_centroid_toward_observation():
    env = DriverPerformanceEnvelope(smoothing=0.5)
    env.ensure("VER", "Flow State")
    env.observe("VER", _state(stress_score=80.0))
    centroid = env.ensure("VER", "Flow State")
    assert centroid.means["stress_score"] > 28.0
    assert centroid.means["stress_score"] < 80.0


def test_envelope_observe_ignored_when_not_fast_signal():
    env = DriverPerformanceEnvelope(smoothing=0.5)
    env.ensure("VER", "Flow State")
    env.observe("VER", _state(stress_score=80.0), is_fast_lap_signal=False)
    centroid = env.ensure("VER", "Flow State")
    assert centroid.means["stress_score"] == pytest.approx(28.0)
    assert centroid.sample_count == 0


def test_envelope_distance_is_positive_when_state_drifts():
    env = DriverPerformanceEnvelope()
    projection = env.project("VER", _state(confidence_score=40.0))
    assert projection.weighted_distance > 0.0
    assert projection.deltas["confidence_score"] == pytest.approx(-44.0)
