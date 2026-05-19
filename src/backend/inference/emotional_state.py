"""Emotional state engine.

The PRD describes a dedicated emotional engine that emits probabilities for
the nine emotional categories (confidence, fear, panic, frustration,
aggression, recovery, overconfidence, hesitation, caution) rather than the
single discrete persona label that the persona drift state machine returns.

The probabilities here are computed from the same cognitive state and the
same feature vector that already drive the cognitive engine, plus the
synthetic biometric stream. The output is a normalised distribution that
sums to one. This makes the dashboard, the audit log, and downstream
reasoners able to compare emotions on equal footing.

Radio tone analysis is explicitly deferred for V1, as documented in the
PRD compliance audit. The engine accepts an optional `radio_features`
argument so a future radio tone module can plug in without rewriting this
module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


EMOTIONS = (
    "confidence",
    "fear",
    "panic",
    "frustration",
    "aggression",
    "recovery",
    "overconfidence",
    "hesitation",
    "caution",
)


@dataclass(frozen=True)
class EmotionalReport:
    driver_id: str
    timestamp: str
    distribution: Dict[str, float]
    dominant_emotion: str
    dominant_probability: float
    rationale: Dict[str, str]


def _saturate(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def evaluate(
    cognitive_state: dict,
    features: dict,
    biometrics: dict,
    radio_features: Optional[dict] = None,
) -> EmotionalReport:
    """Score every emotional category and return a normalised distribution."""

    stress = float(cognitive_state.get("stress_score", 0.0)) / 100.0
    confidence = float(cognitive_state.get("confidence_score", 0.0)) / 100.0
    fatigue = float(cognitive_state.get("fatigue_score", 0.0)) / 100.0
    panic_prob = float(cognitive_state.get("panic_probability", 0.0)) / 100.0
    tunnel_vision = float(cognitive_state.get("tunnel_vision_prob", 0.0)) / 100.0
    cognitive_load = float(cognitive_state.get("cognitive_load_score", 0.0)) / 100.0
    persona = cognitive_state.get("persona_state", "Recovery")

    panic_oscillation = float(features.get("panic_oscillation", 0.0))
    throttle_commitment = float(features.get("throttle_commitment", 0.0)) / 100.0
    braking_hesitation = float(features.get("braking_hesitation", 0.0))
    hrv = float(biometrics.get("synthetic_hrv", 50.0))
    hrv_term = _saturate((50.0 - hrv) / 35.0)  # rises as HRV drops

    radio_tone_anger = 0.0
    if radio_features:
        radio_tone_anger = _saturate(float(radio_features.get("anger_intensity", 0.0)))

    raw: Dict[str, float] = {
        "confidence": _saturate(confidence * 1.1 - panic_prob * 0.5),
        "fear": _saturate(stress * 0.6 + tunnel_vision * 0.4 - confidence * 0.2),
        "panic": _saturate(panic_prob * 0.8 + min(panic_oscillation / 25.0, 1.0) * 0.2),
        "frustration": _saturate(cognitive_load * 0.4 + hrv_term * 0.3 + radio_tone_anger * 0.3),
        "aggression": _saturate(throttle_commitment * 0.6 + (1.0 if persona == "Aggressive" else 0.0) * 0.4),
        "recovery": _saturate((1.0 - stress) * 0.5 + (1.0 if persona == "Recovery" else 0.0) * 0.5),
        "overconfidence": _saturate(max(0.0, confidence - 0.85) * 4.0 * (1.0 - cognitive_load)),
        "hesitation": _saturate(min(braking_hesitation / 1500.0, 1.0) * 0.6 + (1.0 - confidence) * 0.4),
        "caution": _saturate((1.0 - throttle_commitment) * 0.5 + fatigue * 0.3 + (1.0 if persona == "Defensive" else 0.0) * 0.2),
    }

    total = sum(raw.values()) or 1.0
    distribution = {emotion: round(raw[emotion] / total, 4) for emotion in EMOTIONS}

    dominant_emotion = max(distribution, key=lambda key: distribution[key])
    rationale = {
        "confidence": "confidence score above the safety line with low panic probability",
        "fear": "stress and tunnel vision rising against falling confidence",
        "panic": "panic probability or panic oscillation signature elevated",
        "frustration": "cognitive load and HRV compression suggest mental strain",
        "aggression": "throttle commitment high and persona reads Aggressive",
        "recovery": "stress relaxing and persona reads Recovery",
        "overconfidence": "confidence saturating while cognitive load stays low",
        "hesitation": "braking hesitation high and confidence soft",
        "caution": "throttle commitment low or persona reads Defensive",
    }

    return EmotionalReport(
        driver_id=cognitive_state.get("driver_id", ""),
        timestamp=cognitive_state.get("timestamp", ""),
        distribution=distribution,
        dominant_emotion=dominant_emotion,
        dominant_probability=distribution[dominant_emotion],
        rationale=rationale,
    )
