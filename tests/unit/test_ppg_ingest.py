"""Unit tests for live PPG biometric ingestion.

These cover the server side of the PPG sensor pipeline. The browser
side (peak counting in `src/frontend/app/sensor/page.tsx`) is exercised
manually because it depends on the camera API.

The contract the cognitive engine relies on is the payload shape and
the `source: "ppg-camera"` tag, both produced by `build_payload`. The
forwarder behaviour (handling implausible BPM, missing driver, Kafka
errors) is covered with a stubbed producer.
"""

from __future__ import annotations

import json
from typing import List, Tuple

from src.backend.integration import ppg_ingest
from src.backend.integration.ppg_ingest import (
    PPGForwarder,
    PPGSample,
    build_payload,
)


class _StubProducer:
    def __init__(self, raises: bool = False) -> None:
        self.produced: List[Tuple[str, bytes, bytes]] = []
        self.flushed = False
        self.raises = raises

    def produce(self, topic, key, value) -> None:
        if self.raises:
            raise RuntimeError("simulated kafka failure")
        self.produced.append((topic, key, value))

    def poll(self, *_args, **_kwargs) -> None:
        return None

    def flush(self, timeout: float = 5.0) -> int:
        self.flushed = True
        return 0


def _forwarder_with_stub(stub: _StubProducer) -> PPGForwarder:
    forwarder = PPGForwarder.__new__(PPGForwarder)
    forwarder.broker_url = "stub"
    forwarder.producer = stub
    forwarder._dropped_count = 0
    return forwarder


def test_build_payload_valid_sample_emits_canonical_shape():
    sample = PPGSample(driver_id="VER", bpm=82.4, confidence=0.91, timestamp="2026-05-25T20:00:00.000Z")
    payload = build_payload(sample)
    assert payload is not None
    assert payload["driver_id"] == "VER"
    assert payload["synthetic_hr"] == 82.4
    assert payload["source"] == "ppg-camera"
    assert payload["ppg_confidence"] == 0.91
    assert payload["timestamp"] == "2026-05-25T20:00:00.000Z"
    # The cognitive engine expects HRV and respiration even when PPG
    # only provides HR. The neutral defaults must always be present.
    assert "synthetic_hrv" in payload
    assert "respiration_rate" in payload


def test_build_payload_missing_driver_id_returns_none():
    assert build_payload(PPGSample(driver_id="", bpm=80, confidence=0.9)) is None


def test_build_payload_clips_implausible_bpm_low():
    assert build_payload(PPGSample(driver_id="VER", bpm=10, confidence=0.5)) is None


def test_build_payload_clips_implausible_bpm_high():
    assert build_payload(PPGSample(driver_id="VER", bpm=400, confidence=0.5)) is None


def test_build_payload_clamps_confidence_to_unit_interval():
    payload = build_payload(PPGSample(driver_id="VER", bpm=80, confidence=1.5))
    assert payload is not None
    assert payload["ppg_confidence"] == 1.0
    payload_low = build_payload(PPGSample(driver_id="VER", bpm=80, confidence=-0.3))
    assert payload_low is not None
    assert payload_low["ppg_confidence"] == 0.0


def test_forwarder_publishes_to_biometrics_topic():
    stub = _StubProducer()
    forwarder = _forwarder_with_stub(stub)
    ok = forwarder.forward(PPGSample(driver_id="VER", bpm=85.2, confidence=0.8))
    assert ok is True
    assert len(stub.produced) == 1
    topic, key, value = stub.produced[0]
    assert topic == "biometrics-enriched"
    assert key == b"VER"
    parsed = json.loads(value)
    assert parsed["source"] == "ppg-camera"
    assert parsed["synthetic_hr"] == 85.2


def test_forwarder_drops_implausible_sample_without_producing():
    stub = _StubProducer()
    forwarder = _forwarder_with_stub(stub)
    ok = forwarder.forward(PPGSample(driver_id="VER", bpm=12.0, confidence=0.5))
    assert ok is False
    assert stub.produced == []
    assert forwarder.dropped_count == 1


def test_forwarder_drops_missing_driver_without_producing():
    stub = _StubProducer()
    forwarder = _forwarder_with_stub(stub)
    ok = forwarder.forward(PPGSample(driver_id="", bpm=80.0, confidence=0.5))
    assert ok is False
    assert stub.produced == []
    assert forwarder.dropped_count == 1


def test_forwarder_handles_producer_failure_gracefully():
    stub = _StubProducer(raises=True)
    forwarder = _forwarder_with_stub(stub)
    ok = forwarder.forward(PPGSample(driver_id="VER", bpm=85.0, confidence=0.5))
    assert ok is False
    # Failed produce attempts are not counted as drops; they are
    # downstream failures that the caller can decide to retry.
    assert forwarder.dropped_count == 0
