"""Unit tests for the prescription worker loop.

The worker holds three pieces of state: the latest forecast per driver,
the latest Granite explanation per driver, and the producer it publishes
to. These tests exercise each handler in isolation so the Kafka loop
itself does not have to run.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

import pytest

from src.backend.prescription.worker import PRESCRIPTION_TOPIC, PrescriptionWorker


class _RecordingProducer:
    def __init__(self) -> None:
        self.produced: List[Dict[str, Any]] = []

    def produce(self, topic, key, value):  # type: ignore[no-untyped-def]
        self.produced.append({"topic": topic, "key": key, "value": value})

    def poll(self, _timeout):  # type: ignore[no-untyped-def]
        return None


def _make_worker(monkeypatch: pytest.MonkeyPatch, tmp_path) -> PrescriptionWorker:
    monkeypatch.setenv("AUDIT_LOG_DIR", str(tmp_path))
    from src.backend.config import get_settings

    get_settings.cache_clear()

    worker = PrescriptionWorker.__new__(PrescriptionWorker)
    worker.broker_url = "memory:0"
    worker.consumer = None
    worker.producer = _RecordingProducer()
    from src.backend.prescription.engine import PrescriptionEngine

    worker.engine = PrescriptionEngine()
    worker.latest_forecast = {}
    worker.latest_granite = {}
    return worker


def _state(driver_id: str = "VER", **overrides) -> dict:
    base = {
        "driver_id": driver_id,
        "timestamp": "2026-05-20T13:00:00Z",
        "stress_score": 70.0,
        "confidence_score": 35.0,
        "fatigue_score": 45.0,
        "cognitive_load_score": 65.0,
        "attention_stability": 55.0,
        "strategic_reliability": 50.0,
        "panic_probability": 30.0,
        "emotional_drift_score": 10.0,
        "tunnel_vision_prob": 0.0,
        "persona_state": "Defensive",
        "confidence_band": "moderate",
    }
    base.update(overrides)
    return base


def test_anomaly_handler_caches_forecast_per_driver(monkeypatch, tmp_path):
    worker = _make_worker(monkeypatch, tmp_path)
    worker._handle_anomaly({"driver_id": "VER", "horizons": {"5s": {"spin_probability": 0.4}}})
    assert "VER" in worker.latest_forecast
    assert worker.latest_forecast["VER"]["horizons"]["5s"]["spin_probability"] == 0.4


def test_anomaly_handler_ignores_missing_driver(monkeypatch, tmp_path):
    worker = _make_worker(monkeypatch, tmp_path)
    worker._handle_anomaly({"horizons": {}})
    assert worker.latest_forecast == {}


def test_explanation_handler_caches_paragraph(monkeypatch, tmp_path):
    worker = _make_worker(monkeypatch, tmp_path)
    worker._handle_explanation(
        {
            "driver_id": "HAM",
            "explanation": {"text": "calm sequence", "source": "granite-local"},
        }
    )
    assert worker.latest_granite["HAM"]["source"] == "granite-local"


def test_cognitive_handler_emits_prescription(monkeypatch, tmp_path):
    worker = _make_worker(monkeypatch, tmp_path)
    worker._handle_cognitive(_state())
    assert len(worker.producer.produced) == 1
    msg = worker.producer.produced[0]
    assert msg["topic"] == PRESCRIPTION_TOPIC
    payload = json.loads(msg["value"].decode("utf-8"))
    assert payload["driver_id"] == "VER"
    assert "prescription" in payload
    assert "primary" in payload["prescription"]


def test_cognitive_handler_pairs_latest_forecast(monkeypatch, tmp_path):
    worker = _make_worker(monkeypatch, tmp_path)
    worker._handle_anomaly(
        {"driver_id": "VER", "horizons": {"5s": {"spin_probability": 0.9}}}
    )
    worker._handle_cognitive(_state())
    payload = json.loads(worker.producer.produced[0]["value"].decode("utf-8"))
    assert payload["prescription"]["forecast_used"] is True


def test_cognitive_handler_attaches_granite_when_available(monkeypatch, tmp_path):
    worker = _make_worker(monkeypatch, tmp_path)
    worker._handle_explanation(
        {
            "driver_id": "VER",
            "explanation": {"text": "stress trending up", "source": "granite-local"},
        }
    )
    worker._handle_cognitive(_state())
    payload = json.loads(worker.producer.produced[0]["value"].decode("utf-8"))
    assert payload["prescription"]["granite"]["source"] == "granite-local"


def test_cognitive_handler_drops_emit_on_audit_failure(monkeypatch, tmp_path):
    worker = _make_worker(monkeypatch, tmp_path)

    from src.backend.common import audit

    def _raise(_event):
        raise PermissionError("simulated audit failure")

    monkeypatch.setattr(audit, "append", _raise)
    worker._handle_cognitive(_state())
    assert worker.producer.produced == []


def test_cognitive_handler_ignores_missing_driver(monkeypatch, tmp_path):
    worker = _make_worker(monkeypatch, tmp_path)
    worker._handle_cognitive({"timestamp": "2026-05-20T13:00:00Z"})
    assert worker.producer.produced == []
