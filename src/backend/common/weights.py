"""Cognitive engine weight registry.

The values here are the same ones described in `docs/COGNITIVE_METHODOLOGY.md`.
Keeping them in a single Python module lets us stamp them onto every audit log
row, so historical replays remain reproducible after the constants move.

If you change a weight, update the documentation file in the same commit.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


VERSION = "v1.1.0"


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
class CognitiveLoadWeights:
    """Processing burden estimate.

    Combines the variety of simultaneously changing telemetry channels with
    the absolute stress level. A driver lapping a clean track in flow state
    sits below twenty. A driver fighting wet weather in traffic crosses
    seventy.
    """

    micro_correction: float = 0.25
    throttle_jitter: float = 0.20
    panic: float = 0.20
    stress: float = 0.35


@dataclass(frozen=True)
class AttentionStabilityWeights:
    """Focus consistency estimate.

    Higher is better. We invert the destabilising signals and treat
    confidence as a stabiliser. The output stays inside zero to one hundred.
    """

    confidence: float = 0.40
    inv_stress: float = 0.25
    inv_steering_instability: float = 0.20
    inv_micro_correction: float = 0.15


@dataclass(frozen=True)
class StrategicReliabilityWeights:
    """Likelihood of executing the planned strategy.

    Drops when fatigue or panic climb, recovers when confidence and attention
    are intact.
    """

    confidence: float = 0.35
    attention: float = 0.30
    inv_fatigue: float = 0.20
    inv_panic: float = 0.15


@dataclass(frozen=True)
class PanicProbabilityWeights:
    """Discrete probability that the driver tips into a panic episode."""

    panic_oscillation_gain: float = 3.5
    stress_term: float = 0.45
    tunnel_vision_term: float = 0.25


@dataclass(frozen=True)
class EmotionalDriftWeights:
    """Deviation from the rolling baseline emotional stability.

    The cognitive engine keeps a per driver baseline of the last sixty
    confidence scores. Drift is the absolute distance from that baseline
    scaled to zero to one hundred.
    """

    window_size: int = 60
    drift_gain: float = 1.4


@dataclass(frozen=True)
class FailureForecastWeights:
    """Predictive failure engine probability weights.

    Each forecast field is a convex combination of the listed inputs.
    The horizon decay halves the probability as we look further out.
    """

    # crash_likelihood = tunnel*0.5 + stress*0.3 + (1-conf)*0.2
    crash_tunnel: float = 0.5
    crash_stress: float = 0.3
    crash_inv_confidence: float = 0.2

    # lock_up_probability = stress*0.6 + (1-conf)*0.4
    lockup_stress: float = 0.6
    lockup_inv_confidence: float = 0.4

    # spin_probability = (1-conf)*0.5 + stress*0.3 + panic_persona*0.2
    spin_inv_confidence: float = 0.5
    spin_stress: float = 0.3
    spin_panic_persona: float = 0.2

    # failed_overtake = (1-conf)*0.5 + defensive_fatigue_persona*0.5
    overtake_inv_confidence: float = 0.5
    overtake_defensive_fatigue_persona: float = 0.5
    overtake_default_persona_term: float = 0.2

    # concentration_collapse = fatigue*0.4 + stress_recent*0.4 + fatigue_persona*0.2
    collapse_fatigue: float = 0.4
    collapse_stress_recent: float = 0.4
    collapse_fatigue_persona: float = 0.2

    # strategic_noncompliance = aggressive_persona*0.5 + stress*0.3 + (1-conf)*0.2
    noncompliance_aggressive_persona: float = 0.5
    noncompliance_stress: float = 0.3
    noncompliance_inv_confidence: float = 0.2

    horizon_5s: float = 1.0
    horizon_1lap: float = 0.85
    horizon_3laps: float = 0.70
    horizon_full_race: float = 0.55


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
COGNITIVE_LOAD = CognitiveLoadWeights()
ATTENTION = AttentionStabilityWeights()
STRATEGIC = StrategicReliabilityWeights()
PANIC = PanicProbabilityWeights()
EMOTIONAL_DRIFT = EmotionalDriftWeights()
FAILURE = FailureForecastWeights()
PERSONA = PersonaThresholds()


def snapshot() -> dict:
    """Return a serialisable record of the active weights for the audit log."""
    return {
        "version": VERSION,
        "stress": asdict(STRESS),
        "confidence": asdict(CONFIDENCE),
        "fatigue": asdict(FATIGUE),
        "cognitive_load": asdict(COGNITIVE_LOAD),
        "attention_stability": asdict(ATTENTION),
        "strategic_reliability": asdict(STRATEGIC),
        "panic_probability": asdict(PANIC),
        "emotional_drift": asdict(EMOTIONAL_DRIFT),
        "failure_forecast": asdict(FAILURE),
        "persona": asdict(PERSONA),
    }
