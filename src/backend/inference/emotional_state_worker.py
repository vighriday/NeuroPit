"""Emotional state worker.

Subscribes to the cognitive state topic, joins the most recent feature and
biometric payloads per driver, evaluates the emotional distribution, and
publishes the result to the emotional events topic.
"""

from __future__ import annotations

import json
import logging
from typing import Dict, Optional

from confluent_kafka import Consumer, Producer

from src.backend.common import audit
from src.backend.config import get_settings
from src.backend.inference.emotional_state import evaluate

logger = logging.getLogger(__name__)


class EmotionalStateWorker:
    def __init__(self, broker_url: Optional[str] = None):
        settings = get_settings()
        self.broker_url = broker_url or settings.kafka_broker_url

        self.consumer = Consumer(
            {
                "bootstrap.servers": self.broker_url,
                "group.id": "emotional_state_worker_group",
                "auto.offset.reset": "latest",
            }
        )
        self.producer = Producer({"bootstrap.servers": self.broker_url})
        self.consumer.subscribe(
            ["cognitive-state-inference", "telemetry-features", "biometrics-enriched"]
        )

        self.cache: Dict[str, Dict[str, dict]] = {}

    def _store(self, topic: str, data: dict) -> None:
        driver_id = data.get("driver_id")
        if not driver_id:
            return
        bucket = self.cache.setdefault(driver_id, {})
        if topic == "telemetry-features":
            bucket["features"] = data.get("features", data)
        elif topic == "biometrics-enriched":
            bucket["biometrics"] = data
        elif topic == "cognitive-state-inference":
            bucket["cognitive"] = data
            self._emit_if_ready(driver_id, bucket)

    def _emit_if_ready(self, driver_id: str, bucket: dict) -> None:
        cognitive = bucket.get("cognitive")
        features = bucket.get("features") or {}
        biometrics = bucket.get("biometrics") or {}
        if not cognitive:
            return

        report = evaluate(cognitive, features, biometrics)
        payload = {
            "kind": "emotional_state",
            "driver_id": report.driver_id or driver_id,
            "timestamp": report.timestamp,
            "distribution": report.distribution,
            "dominant_emotion": report.dominant_emotion,
            "dominant_probability": report.dominant_probability,
        }

        self.producer.produce(
            "emotional-events",
            key=driver_id.encode("utf-8"),
            value=json.dumps(payload).encode("utf-8"),
        )
        self.producer.poll(0)
        audit.append(payload)

    def run(self) -> None:
        logger.info("Emotional state worker running on broker %s", self.broker_url)
        try:
            while True:
                msg = self.consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    logger.error("Consumer error: %s", msg.error())
                    continue
                try:
                    data = json.loads(msg.value().decode("utf-8"))
                except Exception:
                    continue
                self._store(msg.topic(), data)
        except KeyboardInterrupt:
            logger.info("Shutting down emotional state worker")
        finally:
            self.consumer.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    EmotionalStateWorker().run()
