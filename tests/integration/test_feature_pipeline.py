"""Integration smoke test for the feature pipeline.

Requires a running Redpanda broker on the address configured through the
`KAFKA_BROKER_URL` environment variable. Marked with `pytest.mark.integration`
so the default unit run on a contributor machine does not try to reach a
broker that does not exist.

Run explicitly with:

    pytest -m integration tests/integration

This is the spiritual successor of the original `test_phase_2.py` script that
lived next to the backend code. It does the same thing but now follows the
project's testing layout and respects environment configuration.
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
            "group.id": f"integration-test-{uuid.uuid4()}",
            "auto.offset.reset": "latest",
        }
    )
    consumer.subscribe(["telemetry-features"])
    yield producer, consumer
    consumer.close()


def test_pipeline_emits_features(kafka_clients):
    producer, consumer = kafka_clients

    driver_id = "VER"
    session_id = str(uuid.uuid4())
    for i in range(20):
        frame = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "driver_id": driver_id,
            "session_id": session_id,
            "speed": 220.0 + i,
            "rpm": 11000,
            "gear": 6,
            "throttle": 80.0,
            "brake": 0.0 if i % 2 == 0 else 5.0,
            "steering_angle": (i % 5) - 2.0,
            "drs": 0,
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
            "status": "OnTrack",
        }
        producer.produce(
            "incoming-telemetry-raw",
            key=driver_id.encode("utf-8"),
            value=json.dumps(frame).encode("utf-8"),
        )
    producer.flush()

    deadline = time.time() + 15
    received = []
    while time.time() < deadline and len(received) < 1:
        msg = consumer.poll(1.0)
        if msg is None or msg.error():
            continue
        received.append(json.loads(msg.value().decode("utf-8")))

    assert received, "expected at least one feature window from the pipeline"
    assert received[0]["driver_id"] == driver_id
    assert "features" in received[0]
