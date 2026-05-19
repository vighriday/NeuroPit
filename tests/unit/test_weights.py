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
        "persona",
    }


def test_dataclasses_are_frozen():
    import dataclasses

    for cls in [weights.StressWeights, weights.ConfidenceWeights, weights.FatigueWeights, weights.PersonaThresholds]:
        assert dataclasses.is_dataclass(cls)
        assert getattr(cls, "__dataclass_params__").frozen is True
