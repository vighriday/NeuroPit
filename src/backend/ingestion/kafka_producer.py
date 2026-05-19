"""Kafka producer used by every NeuroPit ingestion path.

The producer is intentionally thin. It does one job, which is to push well
formed telemetry frames and race events into the right Redpanda topic with a
sensible delivery contract. Latency matters here, so we keep batching small
and we never block on a successful delivery callback.
"""

from __future__ import annotations

import logging
from typing import Optional

from confluent_kafka import Producer

from src.backend.config import get_settings
from src.backend.ingestion.models import RaceEvent, TelemetryFrame

logger = logging.getLogger(__name__)


class NeuroPitKafkaProducer:
    """Thin wrapper around confluent_kafka.Producer with project defaults."""

    TELEMETRY_TOPIC = "incoming-telemetry-raw"
    EVENT_TOPIC = "incoming-race-events"

    def __init__(self, broker_url: Optional[str] = None):
        settings = get_settings()
        self.broker_url = broker_url or settings.kafka_broker_url
        self.producer = Producer({
            "bootstrap.servers": self.broker_url,
            "client.id": "neuropit_telemetry_producer",
            "linger.ms": 5,
            "compression.type": "lz4",
        })

    def _delivery_report(self, err, msg):
        if err is not None:
            logger.error("Message delivery failed: %s", err)

    def produce_telemetry(self, frame: TelemetryFrame) -> None:
        """Push a single telemetry frame to the raw telemetry topic."""
        payload = frame.model_dump_json()
        self.producer.produce(
            topic=self.TELEMETRY_TOPIC,
            key=frame.driver_id.encode("utf-8"),
            value=payload.encode("utf-8"),
            callback=self._delivery_report,
        )
        self.producer.poll(0)

    def produce_event(self, event: RaceEvent) -> None:
        """Push a single race event to the race events topic."""
        payload = event.model_dump_json()
        key = event.driver_id.encode("utf-8") if event.driver_id else b"global"
        self.producer.produce(
            topic=self.EVENT_TOPIC,
            key=key,
            value=payload.encode("utf-8"),
            callback=self._delivery_report,
        )
        self.producer.poll(0)

    def flush(self) -> None:
        """Block until every outstanding message is delivered."""
        logger.info("Flushing Kafka producer for broker %s", self.broker_url)
        self.producer.flush()
