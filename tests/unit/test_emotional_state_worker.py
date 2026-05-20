"""Unit tests for the emotional state worker join loop."""

from __future__ import annotations

import json
from typing import Any, Dict, List

import pytest

from src.backend.inference.emotional_state_worker import EmotionalStateWorker


class _RecordingProducer:
    def __init__(self) -> None:
        self.produced: List[Dict[str, Any]] = []

    def produce(self, topic, key, value):  # type: ignore[no-untyped-def]
        self.produced.append({"topic": topic, "key": key, "value": value})

    def poll(self, _timeout):  # type: ignore[no-untyped-def]
        return None


def _worker(monkeypatch: pytest.MonkeyPatch, tmp_path) -> EmotionalStateWorker:
    monkeypatch.setenv("AUDIT_LOG_DIR", str(tmp_path))
    from src.backend.config import get_settings

    get_settings.cache_clear()

    worker = EmotionalStateWorker.__new__(EmotionalStateWorker)
    worker.broker_url = "memory:0"
    worker.consumer = None
    worker.producer = _RecordingProducer()
    worker.cache = {}
    return worker


def _features(driver_id: str = "VER") -> dict:
    return {
        "driver_id": driver_id,
        "features": {
            "steering_instability": 5.0,
            "throttle_jitter": 4.0,
            "panic_oscillation": 3.0,
            "micro_correction_freq": 2.0,
        },
    }


def _biometrics(driver_id: str = "VER") -> dict:
    return {
        "driver_id": driver_id,
        "synthetic_hr": 160.0,
        "synthetic_hrv": 35.0,
    }


def _cognitive(driver_id: str = "VER") -> dict:
    return {
        "driver_id": driver_id,
        "timestamp": "2026-05-20T13:00:00Z",
        "stress_score": 60.0,
        "confidence_score": 50.0,
        "fatigue_score": 30.0,
        "panic_probability": 25.0,
        "emotional_drift_score": 10.0,
        "tunnel_vision_prob": 0.0,
        "persona_state": "Defensive",
        "confidence_band": "moderate",
    }


def test_features_cached_per_driver(monkeypatch, tmp_path):
    worker = _worker(monkeypatch, tmp_path)
    worker._store("telemetry-features", _features("HAM"))
    assert "HAM" in worker.cache
    assert worker.cache["HAM"]["features"]["throttle_jitter"] == 4.0


def test_biometrics_cached_per_driver(monkeypatch, tmp_path):
    worker = _worker(monkeypatch, tmp_path)
    worker._store("biometrics-enriched", _biometrics("VER"))
    assert worker.cache["VER"]["biometrics"]["synthetic_hr"] == 160.0


def test_no_emit_without_cognitive_event(monkeypatch, tmp_path):
    worker = _worker(monkeypatch, tmp_path)
    worker._store("telemetry-features", _features())
    worker._store("biometrics-enriched", _biometrics())
    assert worker.producer.produced == []


def test_emit_when_cognitive_arrives(monkeypatch, tmp_path):
    worker = _worker(monkeypatch, tmp_path)
    worker._store("telemetry-features", _features())
    worker._store("biometrics-enriched", _biometrics())
    worker._store("cognitive-state-inference", _cognitive())

    assert len(worker.producer.produced) == 1
    msg = worker.producer.produced[0]
    assert msg["topic"] == "emotional-events"
    payload = json.loads(msg["value"].decode("utf-8"))
    assert payload["kind"] == "emotional_state"
    assert payload["driver_id"] == "VER"
    assert payload["distribution"]
    assert payload["dominant_emotion"]


def test_missing_driver_id_is_ignored(monkeypatch, tmp_path):
    worker = _worker(monkeypatch, tmp_path)
    worker._store("telemetry-features", {"features": {}})
    assert worker.cache == {}
