"""Unit tests for the shared domain models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.backend.ingestion.models import (
    CognitiveState,
    ConfidenceReport,
    EmotionalState,
    Race,
    Session,
    Simulation,
    StrategyRecommendation,
)


def test_race_model_minimum_fields():
    race = Race(race_id="2021_AbuDhabi", year=2021, event="Abu Dhabi")
    assert race.race_id == "2021_AbuDhabi"


def test_session_links_to_race():
    session = Session(session_id="2021_AbuDhabi_R", race_id="2021_AbuDhabi", session_code="R")
    assert session.race_id == "2021_AbuDhabi"


def test_cognitive_state_rejects_out_of_range_score():
    with pytest.raises(ValidationError):
        CognitiveState(
            driver_id="VER",
            timestamp="2026-05-19T12:00:00Z",
            stress_score=120.0,
            confidence_score=50.0,
            fatigue_score=10.0,
            cognitive_load_score=20.0,
            attention_stability=60.0,
            strategic_reliability=70.0,
            panic_probability=10.0,
            emotional_drift_score=2.0,
            tunnel_vision_prob=0.0,
            persona_state="Recovery",
            confidence_band="moderate",
        )


def test_strategy_recommendation_carries_confidence():
    rec = StrategyRecommendation(
        driver_id="VER",
        timestamp="2026-05-19T12:00:00Z",
        consensus="attack",
        consensus_confidence=0.7,
        margin_over_runner_up=0.25,
        tally={"attack": 1.5, "hold_position": 0.9},
        rationale="aggressive agent backs attack with steady confidence",
    )
    assert rec.consensus_confidence == 0.7


def test_emotional_state_dist():
    state = EmotionalState(
        driver_id="VER",
        timestamp="2026-05-19T12:00:00Z",
        distribution={"confidence": 0.4, "fear": 0.1},
        dominant_emotion="confidence",
        dominant_probability=0.4,
    )
    assert state.dominant_emotion == "confidence"


def test_simulation_payload():
    sim = Simulation(
        scenario="lower_fatigue",
        driver_id="HAM",
        lap_number=30,
        baseline_lap_time_s=91.5,
        counterfactual_lap_time_s=90.7,
        lap_delta_s=-0.8,
        rationale="lower fatigue recovers steering precision",
        adjustments={"fatigue_delta": -25.0},
    )
    assert sim.lap_delta_s == -0.8


def test_confidence_report_rejects_out_of_range_completeness():
    with pytest.raises(ValidationError):
        ConfidenceReport(band="high", data_completeness=1.5, sensor_agreement=0.8)
