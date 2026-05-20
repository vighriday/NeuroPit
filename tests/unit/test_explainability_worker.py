"""Unit tests for the explainability worker.

We bypass Kafka and Granite to keep these tests fast and deterministic.
The point is to confirm the worker writes the expected envelope shape
to the producer and the audit log when a cognitive state arrives.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

import pytest

from src.backend.reasoning.explainability_worker import ExplainabilityWorker


class _RecordingProducer:
    def __init__(self) -> None:
        self.produced: List[Dict[str, Any]] = []

    def produce(self, topic, key, value):  # type: ignore[no-untyped-def]
        self.produced.append({"topic": topic, "key": key, "value": value})

    def poll(self, _timeout):  # type: ignore[no-untyped-def]
        return None


class _StubGranite:
    def explain(self, state):  # type: ignore[no-untyped-def]
        return {
            "text": f"Driver {state.get('driver_id', '?')} explanation",
            "source": "test-stub",
            "model": "test/stub",
            "tokens": 3,
            "grounding": [],
        }


def _worker(monkeypatch: pytest.MonkeyPatch, tmp_path) -> ExplainabilityWorker:
    monkeypatch.setenv("AUDIT_LOG_DIR", str(tmp_path))
    from src.backend.config import get_settings

    get_settings.cache_clear()
    worker = ExplainabilityWorker.__new__(ExplainabilityWorker)
    worker.broker_url = "memory:0"
    worker.consumer = None
    worker.producer = _RecordingProducer()
    worker.granite = _StubGranite()
    return worker


def _state(driver_id: str = "VER") -> dict:
    return {
        "driver_id": driver_id,
        "timestamp": "2026-05-20T13:00:00Z",
        "stress_score": 50.0,
        "confidence_score": 60.0,
        "fatigue_score": 30.0,
        "panic_probability": 20.0,
        "persona_state": "Defensive",
        "confidence_band": "moderate",
    }


def test_handle_state_publishes_explanation_envelope(monkeypatch, tmp_path):
    worker = _worker(monkeypatch, tmp_path)
    payload = worker._handle_state(_state())

    assert payload["kind"] == "explanation"
    assert payload["driver_id"] == "VER"
    assert payload["explanation"]["source"] == "test-stub"
    assert len(worker.producer.produced) == 1
    msg = worker.producer.produced[0]
    assert msg["topic"] == "explanation-events"
    assert msg["key"] == b"VER"


def test_handle_state_falls_back_when_driver_missing(monkeypatch, tmp_path):
    worker = _worker(monkeypatch, tmp_path)
    state = {"timestamp": "2026-05-20T13:00:00Z", "stress_score": 30.0}
    payload = worker._handle_state(state)

    assert payload["driver_id"] is None
    msg = worker.producer.produced[0]
    assert msg["key"] == b"global"


def test_audit_log_records_explanation(monkeypatch, tmp_path):
    worker = _worker(monkeypatch, tmp_path)
    worker._handle_state(_state("HAM"))

    audit_files = list(tmp_path.glob("cognitive-*.jsonl"))
    assert len(audit_files) == 1
    rows = audit_files[0].read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 1
    parsed = json.loads(rows[0])
    assert parsed["driver_id"] == "HAM"
    assert parsed["kind"] == "explanation"
