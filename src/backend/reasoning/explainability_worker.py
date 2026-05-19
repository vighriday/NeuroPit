"""Explainability worker.

Subscribes to the cognitive state topic, asks IBM Granite (or the local stub)
for a short natural language explanation per evaluation, and publishes the
result to the explanation events topic. The dashboard reads from that topic
directly. The audit log keeps a copy too.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from confluent_kafka import Consumer, Producer

from src.backend.common import audit
from src.backend.config import get_settings
from src.backend.reasoning.granite_client import GraniteClient

logger = logging.getLogger(__name__)


class ExplainabilityWorker:
    def __init__(self, broker_url: Optional[str] = None):
        settings = get_settings()
        self.broker_url = broker_url or settings.kafka_broker_url

        self.consumer = Consumer(
            {
                "bootstrap.servers": self.broker_url,
                "group.id": "explainability_worker_group",
                "auto.offset.reset": "latest",
            }
        )
        self.producer = Producer({"bootstrap.servers": self.broker_url})
        self.consumer.subscribe(["cognitive-state-inference"])

        self.granite = GraniteClient(settings)

    def run(self) -> None:
        logger.info("Explainability worker running on broker %s", self.broker_url)
        try:
            while True:
                msg = self.consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    logger.error("Consumer error: %s", msg.error())
                    continue

                state = json.loads(msg.value().decode("utf-8"))
                explanation = self.granite.explain(state)

                payload = {
                    "kind": "explanation",
                    "driver_id": state.get("driver_id"),
                    "timestamp": state.get("timestamp"),
                    "state": state,
                    "explanation": explanation,
                }
                self.producer.produce(
                    "explanation-events",
                    key=str(state.get("driver_id", "global")).encode("utf-8"),
                    value=json.dumps(payload).encode("utf-8"),
                )
                self.producer.poll(0)
                audit.append(payload)

        except KeyboardInterrupt:
            logger.info("Shutting down explainability worker")
        finally:
            self.consumer.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ExplainabilityWorker().run()
