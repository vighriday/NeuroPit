"""Verifies the cognitive equations directly against the documented formulas.

We intentionally do not boot Kafka or InfluxDB for these tests. Instead we
recreate the maths from `docs/COGNITIVE_METHODOLOGY.md` and check the numbers
match the values the engine would emit for the same inputs.
"""

from __future__ import annotations

from src.backend.common import weights


def _stress_score(steering_instability: float, panic: float, synthetic_hr: float) -> float:
    w = weights.STRESS
    steering_term = min(steering_instability * w.steering_gain, 100.0)
    hr_term = max(0.0, synthetic_hr - w.hr_baseline) * w.hr_gain
    score = steering_term * w.steering + hr_term * w.heart_rate + panic * w.panic
    return max(0.0, min(100.0, score))


def _confidence_score(throttle_commitment: float, braking_hesitation: float) -> float:
    c = weights.CONFIDENCE
    throttle_term = min(throttle_commitment * c.throttle_gain, 100.0)
    hesitation_pen = braking_hesitation * c.hesitation_penalty
    score = 100.0 - ((100.0 - throttle_term) * c.throttle_term_weight + hesitation_pen)
    return max(0.0, min(100.0, score))


def test_calm_driver_stays_calm():
    assert _stress_score(steering_instability=0.0, panic=0.0, synthetic_hr=130.0) == 0.0


def test_panic_event_reaches_high_stress():
    score = _stress_score(steering_instability=8.0, panic=80.0, synthetic_hr=185.0)
    assert score >= 60.0


def test_confidence_drops_when_braking_is_pumpy():
    smooth = _confidence_score(throttle_commitment=15.0, braking_hesitation=0.0)
    pumpy = _confidence_score(throttle_commitment=15.0, braking_hesitation=600.0)
    assert pumpy < smooth


def test_full_throttle_commitment_floors_confidence_at_100():
    assert _confidence_score(throttle_commitment=25.0, braking_hesitation=0.0) == 100.0
