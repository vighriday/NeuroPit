"""Unit tests for the strategy parliament."""

from __future__ import annotations

from src.backend.strategy import parliament
from src.backend.strategy.parliament import (
    ALLOWED_PROPOSALS,
    ATTACK,
    DEFEND,
    HOLD_POSITION,
    PIT_NOW,
    STAY_OUT,
    convene,
)


def _state(**overrides) -> dict:
    base = {
        "driver_id": "VER",
        "stress_score": 40.0,
        "confidence_score": 70.0,
        "fatigue_score": 20.0,
        "persona_state": "Recovery",
        "tire_wear": 0.5,
        "rain_probability": 0.1,
        "gap_to_car_ahead_s": 2.5,
    }
    base.update(overrides)
    return base


def test_every_agent_emits_an_allowed_proposal():
    report = convene(_state())
    assert len(report.proposals) == 7
    for prop in report.proposals:
        assert prop.proposal in ALLOWED_PROPOSALS
        assert 0.0 <= prop.confidence <= 1.0


def test_high_rain_probability_lands_a_pit_vote():
    report = convene(_state(rain_probability=0.85))
    assert report.tally.get(PIT_NOW, 0.0) > 0.0


def test_panic_persona_avoids_attack_consensus():
    report = convene(_state(stress_score=92.0, confidence_score=20.0, persona_state="Panic"))
    assert report.consensus != ATTACK


def test_transcript_lists_every_agent():
    report = convene(_state())
    for agent_name in ("aggressive", "defensive", "tire_preservation", "weather_risk", "cognitive_stability", "overtake_optimization", "fatigue_management"):
        assert agent_name in report.transcript


def test_margin_is_non_negative():
    report = convene(_state())
    assert report.margin_over_runner_up >= 0.0
