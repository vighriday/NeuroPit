"""Integration smoke test for the cognitive inference pipeline.

Requires a running Redpanda broker. Replaces the old `test_phase_3.py` script.
Sends synthetic features and biometrics directly into the appropriate topics
and asserts that the cognitive engine emits a state.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def kafka_clients():
    confluent = pytest.importorskip("confluent_kafka")
    from src.backend.config import get_settings

    settings = get_settings()
    producer = confluent.Producer({"bootstrap.servers": settings.kafka_broker_url})
    consumer = confluent.Consumer(
        {
            "bootstrap.servers": settings.kafka_broker_url,
            "group.id": f"integration-cognitive-{uuid.uuid4()}",
            "auto.offset.reset": "latest",
        }
    )
    consumer.subscribe(["cognitive-state-inference"])
    yield producer, consumer
    consumer.close()


def test_cognitive_state_is_emitted(kafka_clients):
    producer, consumer = kafka_clients
    driver_id = "VER"
    timestamp = datetime.now(timezone.utc).isoformat()

    features = {
        "timestamp": timestamp,
        "driver_id": driver_id,
        "session_id": "integration",
        "features": {
            "steering_instability": 12.0,
            "braking_hesitation": 400.0,
            "throttle_commitment": 25.0,
            "panic_oscillation": 8.0,
        },
    }
    biometrics = {
        "timestamp": timestamp,
        "driver_id": driver_id,
        "synthetic_hr": 172.0,
        "synthetic_hrv": 28.0,
        "respiration_rate": 26.0,
        "source": "synthetic",
    }
    producer.produce(
        "telemetry-features",
        key=driver_id.encode("utf-8"),
        value=json.dumps(features).encode("utf-8"),
    )
    producer.produce(
        "biometrics-enriched",
        key=driver_id.encode("utf-8"),
        value=json.dumps(biometrics).encode("utf-8"),
    )
    producer.flush()

    deadline = time.time() + 20
    cognitive = None
    while time.time() < deadline and cognitive is None:
        msg = consumer.poll(1.0)
        if msg is None or msg.error():
            continue
        cognitive = json.loads(msg.value().decode("utf-8"))

    assert cognitive is not None, "expected a cognitive state event"
    assert cognitive["driver_id"] == driver_id
    assert 0.0 <= cognitive["stress_score"] <= 100.0
    assert cognitive["persona_state"] in {
        "Panic",
        "Aggressive",
        "Fatigue",
        "Defensive",
        "Flow State",
        "Recovery",
    }
    assert cognitive["confidence_band"] in {"high", "moderate", "unstable"}
