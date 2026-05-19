"""Unit tests for the persona drift state machine."""

from __future__ import annotations

from src.backend.common import persona


def test_panic_takes_priority():
    assert (
        persona.classify(
            stress=90.0,
            confidence=10.0,
            fatigue=70.0,
            panic_oscillation=25.0,
            throttle_commitment=90.0,
        )
        == "Panic"
    )


def test_aggressive_when_stress_high_and_throttle_committed():
    assert (
        persona.classify(
            stress=75.0,
            confidence=60.0,
            fatigue=20.0,
            panic_oscillation=5.0,
            throttle_commitment=90.0,
        )
        == "Aggressive"
    )


def test_fatigue_when_tired_and_unsure():
    assert (
        persona.classify(
            stress=50.0,
            confidence=20.0,
            fatigue=80.0,
            panic_oscillation=5.0,
            throttle_commitment=50.0,
        )
        == "Fatigue"
    )


def test_defensive_on_low_confidence():
    assert (
        persona.classify(
            stress=50.0,
            confidence=40.0,
            fatigue=10.0,
            panic_oscillation=5.0,
            throttle_commitment=50.0,
        )
        == "Defensive"
    )


def test_flow_state_when_calm_and_decisive():
    assert (
        persona.classify(
            stress=20.0,
            confidence=90.0,
            fatigue=10.0,
            panic_oscillation=5.0,
            throttle_commitment=70.0,
        )
        == "Flow State"
    )


def test_recovery_is_the_default():
    assert (
        persona.classify(
            stress=55.0,
            confidence=70.0,
            fatigue=20.0,
            panic_oscillation=5.0,
            throttle_commitment=60.0,
        )
        == "Recovery"
    )
