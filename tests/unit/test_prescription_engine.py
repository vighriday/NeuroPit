"""Unit tests for the Cognitive Prescriptive Engine."""

from __future__ import annotations

import pytest

from src.backend.prescription.engine import PrescriptionEngine
from src.backend.prescription.actions import ACTION_SPACE, guardrails_blocked


def _flow_state():
    return {
        "driver_id": "VER",
        "timestamp": "2026-05-19T12:00:00Z",
        "stress_score": 28.0,
        "confidence_score": 84.0,
        "fatigue_score": 24.0,
        "cognitive_load_score": 38.0,
        "attention_stability": 80.0,
        "strategic_reliability": 80.0,
        "panic_probability": 4.0,
        "emotional_drift_score": 10.0,
        "tunnel_vision_prob": 0.0,
        "persona_state": "Flow State",
        "confidence_band": "high",
    }


def test_flow_state_yields_hold_or_push():
    engine = PrescriptionEngine()
    prescription = engine.emit(_flow_state())
    assert prescription.primary.code in {"hold_position", "radio_push"}
    assert prescription.optimality.cognitive_efficiency > 90.0


def test_panic_yields_box_now():
    engine = PrescriptionEngine()
    state = _flow_state()
    state.update(
        {
            "stress_score": 88.0,
            "confidence_score": 32.0,
            "panic_probability": 82.0,
            "cognitive_load_score": 88.0,
            "persona_state": "Panic",
            "tunnel_vision_prob": 60.0,
            "confidence_band": "unstable",
        }
    )
    prescription = engine.emit(state)
    assert prescription.primary.code == "box_now"
    assert prescription.optimality.performance_lost_s > 0.0


def test_guardrail_blocks_push_when_panic_high():
    state = _flow_state()
    state["panic_probability"] = 70.0
    assert guardrails_blocked("radio_push", state) != []


def test_guardrail_blocks_undercut_when_confidence_low():
    state = _flow_state()
    state["confidence_score"] = 40.0
    assert guardrails_blocked("request_undercut_window", state) != []


def test_blocked_actions_drop_below_primary():
    engine = PrescriptionEngine()
    state = _flow_state()
    state.update(
        {
            "stress_score": 78.0,
            "panic_probability": 70.0,
            "confidence_score": 72.0,
        }
    )
    prescription = engine.emit(state)
    assert prescription.primary.code != "radio_push"


def test_action_space_codes_are_unique():
    codes = [a.code for a in ACTION_SPACE]
    assert len(codes) == len(set(codes))


def test_forecast_drives_box_when_collapse_high():
    engine = PrescriptionEngine()
    state = _flow_state()
    state.update({"confidence_band": "moderate", "stress_score": 60.0, "panic_probability": 35.0})
    forecast = {"horizons": {"5s": {"panic_collapse": 0.75, "confidence_collapse": 0.5}}}
    prescription = engine.emit(state, forecast=forecast)
    assert prescription.forecast_used is True
    assert prescription.primary.code in {"box_now", "radio_calm"}


def test_projected_twin_clips_to_zero_hundred():
    engine = PrescriptionEngine()
    state = _flow_state()
    state.update({"stress_score": 5.0, "confidence_score": 98.0, "panic_probability": 2.0})
    prescription = engine.emit(state)
    for value in prescription.primary.projected_twin.values():
        assert 0.0 <= value <= 100.0


def test_rationale_mentions_persona_and_efficiency():
    engine = PrescriptionEngine()
    prescription = engine.emit(_flow_state())
    rationale = prescription.rationale.lower()
    assert "flow state" in rationale
    assert "/100" in rationale or "efficiency" in rationale
