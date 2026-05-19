"""Persona drift state machine.

Maps continuous cognitive scores to one of six discrete labels described in
`docs/COGNITIVE_METHODOLOGY.md`. The rules are evaluated in order and the
first match wins.
"""

from __future__ import annotations

from src.backend.common.weights import PERSONA


def classify(stress: float, confidence: float, fatigue: float, panic_oscillation: float, throttle_commitment: float) -> str:
    if stress > PERSONA.panic_stress and panic_oscillation > PERSONA.panic_oscillation:
        return "Panic"
    if stress > PERSONA.aggressive_stress and throttle_commitment > PERSONA.aggressive_throttle:
        return "Aggressive"
    if fatigue > PERSONA.fatigue_score and confidence < PERSONA.fatigue_confidence:
        return "Fatigue"
    if confidence < PERSONA.defensive_confidence:
        return "Defensive"
    if stress < PERSONA.flow_stress and confidence > PERSONA.flow_confidence:
        return "Flow State"
    return "Recovery"
