"""Unit tests for the trust and uncertainty layer."""

from __future__ import annotations

from src.backend.common import uncertainty


def test_full_frame_is_complete():
    frame = {
        "speed": 200.0,
        "rpm": 11000,
        "gear": 5,
        "throttle": 90.0,
        "brake": 0.0,
        "steering_angle": 2.0,
    }
    assert uncertainty.data_completeness(frame) == 1.0


def test_missing_fields_lower_completeness():
    frame = {"speed": 200.0, "rpm": 11000}
    completeness = uncertainty.data_completeness(frame)
    assert 0.0 < completeness < 1.0


def test_sensor_agreement_full_consensus():
    assert uncertainty.sensor_agreement([1.0, 2.0, 0.5]) == 1.0


def test_sensor_agreement_mixed_signals():
    assert uncertainty.sensor_agreement([1.0, -1.0, 1.0]) == 2 / 3


def test_sensor_agreement_ignores_neutral_values():
    assert uncertainty.sensor_agreement([0.0, 0.0]) == 1.0


def test_evaluate_returns_high_band_for_complete_agreement():
    frame = {
        "speed": 200.0,
        "rpm": 11000,
        "gear": 5,
        "throttle": 90.0,
        "brake": 0.0,
        "steering_angle": 2.0,
    }
    report = uncertainty.evaluate(frame, [1.0, 1.0, 1.0, 1.0])
    assert report.band == "high"
    assert report.data_completeness == 1.0


def test_evaluate_downgrades_when_data_is_sparse():
    frame = {"speed": 200.0}
    report = uncertainty.evaluate(frame, [1.0])
    assert report.band == "unstable"
