"""Unit tests for the cognitive weight registry.

The registry is the audit trail companion of the cognitive engine. These
tests make sure the snapshot is JSON serialisable and that nobody accidentally
mutates the constants at import time.
"""

from __future__ import annotations

import json

from src.backend.common import weights


def test_snapshot_is_json_serialisable():
    snap = weights.snapshot()
    payload = json.dumps(snap)
    restored = json.loads(payload)
    assert restored["version"] == weights.VERSION
    assert restored["stress"]["steering"] == weights.STRESS.steering


def test_snapshot_contains_every_section():
    snap = weights.snapshot()
    assert set(snap.keys()) == {
        "version",
        "stress",
        "confidence",
        "fatigue",
        "cognitive_load",
        "attention_stability",
        "strategic_reliability",
        "panic_probability",
        "emotional_drift",
        "failure_forecast",
        "prescription",
        "persona",
    }


def test_failure_forecast_weights_sum_to_one_per_probability():
    fw = weights.FAILURE
    assert fw.crash_tunnel + fw.crash_stress + fw.crash_inv_confidence == 1.0
    assert fw.lockup_stress + fw.lockup_inv_confidence == 1.0
    assert fw.spin_inv_confidence + fw.spin_stress + fw.spin_panic_persona == 1.0
    assert (
        fw.overtake_inv_confidence + fw.overtake_defensive_fatigue_persona == 1.0
    )
    assert (
        fw.collapse_fatigue + fw.collapse_stress_recent + fw.collapse_fatigue_persona == 1.0
    )
    assert (
        fw.noncompliance_aggressive_persona
        + fw.noncompliance_stress
        + fw.noncompliance_inv_confidence
        == 1.0
    )


def test_failure_horizon_decay_is_monotonic():
    fw = weights.FAILURE
    horizons = [fw.horizon_5s, fw.horizon_1lap, fw.horizon_3laps, fw.horizon_full_race]
    assert horizons == sorted(horizons, reverse=True)
    assert 0.0 < horizons[-1] < horizons[0] <= 1.0


def test_dataclasses_are_frozen():
    import dataclasses

    for cls in [weights.StressWeights, weights.ConfidenceWeights, weights.FatigueWeights, weights.PersonaThresholds]:
        assert dataclasses.is_dataclass(cls)
        assert getattr(cls, "__dataclass_params__").frozen is True
