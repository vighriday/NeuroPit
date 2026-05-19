"""Unit tests for the behavioural feature engine.

These tests exercise the signal processor on hand crafted windows so we can
say with confidence what each feature does when the inputs are quiet, when
they are noisy, and when they look like a real panic event.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

import pytest

from src.backend.feature_engineering.signal_processor import SignalProcessor
from src.backend.ingestion.models import TelemetryFrame


def _frame(steering: float = 0.0, throttle: float = 0.0, brake: float = 0.0) -> TelemetryFrame:
    return TelemetryFrame(
        timestamp=datetime.now(timezone.utc),
        driver_id="VER",
        session_id="unit-test",
        speed=200.0,
        rpm=11000,
        gear=5,
        throttle=throttle,
        brake=brake,
        steering_angle=steering,
        drs=0,
        x=0.0,
        y=0.0,
        z=0.0,
    )


def _window(values: List[dict]) -> List[TelemetryFrame]:
    return [_frame(**v) for v in values]


def test_empty_window_returns_zeros():
    processor = SignalProcessor(sample_rate_hz=10.0)
    features = processor.process_window([])
    assert features == {
        "steering_instability": 0.0,
        "braking_hesitation": 0.0,
        "throttle_commitment": 0.0,
        "panic_oscillation": 0.0,
    }


def test_steady_steering_is_calm():
    processor = SignalProcessor(sample_rate_hz=10.0)
    window = _window([{"steering": 1.0}] * 20)
    features = processor.process_window(window)
    assert features["steering_instability"] == pytest.approx(0.0, abs=1e-6)
    assert features["panic_oscillation"] == 0.0


def test_oscillating_steering_lifts_instability():
    processor = SignalProcessor(sample_rate_hz=10.0)
    window = _window([{"steering": v} for v in [-15, 15, -15, 15, -15, 15, -15, 15, -15, 15, -15, 15]])
    features = processor.process_window(window)
    assert features["steering_instability"] > 0.0
    assert features["panic_oscillation"] > 0.0


def test_throttle_commitment_picks_largest_positive_gradient():
    processor = SignalProcessor(sample_rate_hz=10.0)
    window = _window([{"throttle": v} for v in [10, 20, 22, 24, 90, 92, 94, 95, 96, 97, 98]])
    features = processor.process_window(window)
    assert features["throttle_commitment"] == pytest.approx(66.0, abs=1e-3)


def test_brake_pumping_raises_hesitation():
    processor = SignalProcessor(sample_rate_hz=10.0)
    window = _window([{"brake": v} for v in [40, 10, 60, 5, 70, 8, 80, 12, 90, 6, 100, 2]])
    features = processor.process_window(window)
    assert features["braking_hesitation"] > 0.0


def test_steady_braking_has_no_hesitation():
    processor = SignalProcessor(sample_rate_hz=10.0)
    window = _window([{"brake": v} for v in [80] * 12])
    features = processor.process_window(window)
    assert features["braking_hesitation"] == 0.0


def test_panic_signature_combines_steering_and_pedal_overlap():
    processor = SignalProcessor(sample_rate_hz=10.0)
    window = _window(
        [
            {"steering": s, "throttle": 60.0, "brake": 60.0}
            for s in [-30, 30, -30, 30, -30, 30, -30, 30, -30, 30, -30, 30]
        ]
    )
    features = processor.process_window(window)
    assert features["panic_oscillation"] > 5.0
