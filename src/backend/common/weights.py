"""Cognitive engine weight registry.

The values here are the same ones described in `docs/COGNITIVE_METHODOLOGY.md`.
Keeping them in a single Python module lets us stamp them onto every audit log
row, so historical replays remain reproducible after the constants move.

If you change a weight, update the documentation file in the same commit.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


VERSION = "v1.0.0"


@dataclass(frozen=True)
class StressWeights:
    steering: float = 0.40
    heart_rate: float = 0.40
    panic: float = 0.20
    hr_baseline: float = 140.0
    hr_gain: float = 1.5
    steering_gain: float = 10.0


@dataclass(frozen=True)
class ConfidenceWeights:
    throttle_gain: float = 5.0
    hesitation_penalty: float = 0.05
    throttle_term_weight: float = 0.60


@dataclass(frozen=True)
class FatigueWeights:
    stress_term: float = 0.0005
    steering_term: float = 0.001


@dataclass(frozen=True)
class PersonaThresholds:
    panic_stress: float = 85.0
    panic_oscillation: float = 20.0
    aggressive_stress: float = 70.0
    aggressive_throttle: float = 80.0
    fatigue_score: float = 60.0
    fatigue_confidence: float = 40.0
    defensive_confidence: float = 50.0
    flow_stress: float = 40.0
    flow_confidence: float = 80.0


STRESS = StressWeights()
CONFIDENCE = ConfidenceWeights()
FATIGUE = FatigueWeights()
PERSONA = PersonaThresholds()


def snapshot() -> dict:
    """Return a serialisable record of the active weights for the audit log."""
    return {
        "version": VERSION,
        "stress": asdict(STRESS),
        "confidence": asdict(CONFIDENCE),
        "fatigue": asdict(FATIGUE),
        "persona": asdict(PERSONA),
    }
