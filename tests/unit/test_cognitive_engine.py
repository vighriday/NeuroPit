"""Verifies the cognitive engine emits the full nine score twin.

We bypass Kafka and InfluxDB by exercising the `evaluate` method directly
against a hand built cache. This keeps the test fast while still validating
the documented contract.
"""

from __future__ import annotations

from src.backend.inference.cognitive_engine import CognitiveInferenceEngine


def _engine() -> CognitiveInferenceEngine:
    engine = CognitiveInferenceEngine.__new__(CognitiveInferenceEngine)
    from src.backend.common import weights as weights_module

    engine.weights_snapshot = weights_module.snapshot()
    engine.producer = type("P", (), {"produce": lambda *a, **k: None, "poll": lambda *a, **k: None})()
    engine.influx_bucket = "test"
    engine.influx_org = "test"

    class _NoopWriter:
        def write(self, *args, **kwargs):
            return None

    engine.write_api = _NoopWriter()
    from collections import deque

    engine.state_cache = {}
    engine._cache_factory_window = weights_module.EMOTIONAL_DRIFT.window_size

    def _make_cache():
        return {
            "features": {},
            "biometrics": {},
            "cumulative_fatigue": 0.0,
            "confidence_history": deque(maxlen=weights_module.EMOTIONAL_DRIFT.window_size),
        }

    engine._make_cache = _make_cache  # type: ignore[attr-defined]
    return engine


def _cache(engine: CognitiveInferenceEngine, driver_id: str = "VER"):
    cache = engine._make_cache()  # type: ignore[attr-defined]
    engine.state_cache[driver_id] = cache
    return cache


def test_evaluate_emits_full_nine_score_twin(monkeypatch):
    engine = _engine()
    cache = _cache(engine)
    cache["features"] = {
        "timestamp": "2026-05-19T12:00:00Z",
        "driver_id": "VER",
        "session_id": "test",
        "features": {
            "steering_instability": 8.0,
            "braking_hesitation": 500.0,
            "throttle_commitment": 25.0,
            "panic_oscillation": 12.0,
            "micro_correction_freq": 6.0,
            "throttle_jitter": 30.0,
            "line_consistency": 70.0,
            "reaction_smoothness": 65.0,
        },
    }
    cache["biometrics"] = {
        "driver_id": "VER",
        "synthetic_hr": 175.0,
        "synthetic_hrv": 28.0,
    }

    state = engine.evaluate("VER", "2026-05-19T12:00:00Z", cache)

    for field_name in (
        "stress_score",
        "confidence_score",
        "fatigue_score",
        "cognitive_load_score",
        "attention_stability",
        "strategic_reliability",
        "panic_probability",
        "emotional_drift_score",
        "tunnel_vision_prob",
    ):
        assert field_name in state, f"missing {field_name}"
        assert 0.0 <= float(state[field_name]) <= 100.0, f"{field_name} out of range"

    assert state["persona_state"] in {
        "Panic",
        "Aggressive",
        "Fatigue",
        "Defensive",
        "Flow State",
        "Recovery",
    }
    assert state["confidence_band"] in {"high", "moderate", "unstable"}
    assert state["weights_version"]
    assert state["context"]["line_consistency"] == 70.0


def test_emotional_drift_grows_with_confidence_swings():
    engine = _engine()
    cache = _cache(engine, "VER")

    base_features = {
        "timestamp": "2026-05-19T12:00:00Z",
        "driver_id": "VER",
        "session_id": "test",
        "features": {
            "steering_instability": 5.0,
            "braking_hesitation": 200.0,
            "throttle_commitment": 25.0,
            "panic_oscillation": 5.0,
            "micro_correction_freq": 4.0,
            "throttle_jitter": 10.0,
            "line_consistency": 80.0,
            "reaction_smoothness": 75.0,
        },
    }
    cache["features"] = base_features
    cache["biometrics"] = {"driver_id": "VER", "synthetic_hr": 150.0, "synthetic_hrv": 50.0}

    drifts = []
    for hr in (150.0, 150.0, 150.0, 150.0, 150.0, 190.0):
        cache["biometrics"] = {"driver_id": "VER", "synthetic_hr": hr, "synthetic_hrv": 45.0}
        state = engine.evaluate("VER", "2026-05-19T12:00:00Z", cache)
        drifts.append(state["emotional_drift_score"])

    assert drifts[-1] >= drifts[0]
