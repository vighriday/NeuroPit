"""Prescription worker.

Joins the cognitive state stream with the predictive failure forecast,
runs the prescriptive engine, asks IBM Granite to write a short
operational explanation that grounds the prescription, and publishes the
result to the `cognitive-prescriptions` topic. The dashboard reads from
that topic over the gateway websocket. Every prescription is audited.

The worker holds the latest forecast per driver in memory and pairs it
with the next cognitive event for the same driver. If no forecast has
arrived yet the prescription is emitted without one and the `forecast_used`
flag is False.
"""

from __future__ import annotations

import json
import logging
from typing import Dict, Optional

from confluent_kafka import Consumer, Producer

from src.backend.common import audit
from src.backend.config import get_settings
from src.backend.prescription.engine import PrescriptionEngine
from src.backend.reasoning.granite_client import GraniteClient

logger = logging.getLogger(__name__)


PRESCRIPTION_TOPIC = "cognitive-prescriptions"


class PrescriptionWorker:
    """Joins cognitive state with forecasts and emits prescriptions."""

    def __init__(self, broker_url: Optional[str] = None):
        settings = get_settings()
        self.broker_url = broker_url or settings.kafka_broker_url

        self.consumer = Consumer(
            {
                "bootstrap.servers": self.broker_url,
                "group.id": "prescription_worker_group",
                "auto.offset.reset": "latest",
            }
        )
        self.producer = Producer({"bootstrap.servers": self.broker_url})
        self.consumer.subscribe(["cognitive-state-inference", "anomaly-events"])

        self.engine = PrescriptionEngine()
        self.latest_forecast: Dict[str, dict] = {}
        self.granite = GraniteClient(settings)

    def _enrich_with_granite(self, prescription_dict: dict, state: dict) -> dict:
        try:
            hint = (
                f"Primary action {prescription_dict['primary']['label']} "
                f"with efficiency {prescription_dict['optimality']['cognitive_efficiency']:.0f}/100. "
                f"Estimated lap delta {prescription_dict['optimality']['performance_lost_s']:.2f}s."
            )
            explanation = self.granite.explain(state, prompt_hint=hint)
            return explanation
        except Exception as exc:
            logger.debug("Granite enrichment skipped: %s", exc)
            return {}

    def _handle_anomaly(self, data: dict) -> None:
        driver_id = str(data.get("driver_id") or "")
        if not driver_id:
            return
        self.latest_forecast[driver_id] = data

    def _handle_cognitive(self, data: dict) -> None:
        driver_id = str(data.get("driver_id") or "")
        if not driver_id:
            return
        forecast = self.latest_forecast.get(driver_id)
        prescription = self.engine.emit(state=data, forecast=forecast)
        prescription_dict = prescription.to_dict()

        granite = self._enrich_with_granite(prescription_dict, data)
        if granite:
            prescription_dict["granite"] = granite

        payload = {
            "kind": "prescription",
            "driver_id": driver_id,
            "timestamp": data.get("timestamp"),
            "prescription": prescription_dict,
        }
        self.producer.produce(
            PRESCRIPTION_TOPIC,
            key=driver_id.encode("utf-8"),
            value=json.dumps(payload, default=str).encode("utf-8"),
        )
        self.producer.poll(0)
        audit.append({"kind": "prescription_emission", **payload})

    def run(self) -> None:
        logger.info("Prescription worker running on broker %s", self.broker_url)
        try:
            while True:
                msg = self.consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    logger.error("Prescription consumer error: %s", msg.error())
                    continue
                topic = msg.topic()
                try:
                    data = json.loads(msg.value().decode("utf-8"))
                except Exception:
                    continue
                if topic == "anomaly-events":
                    self._handle_anomaly(data)
                elif topic == "cognitive-state-inference":
                    self._handle_cognitive(data)
        except KeyboardInterrupt:
            logger.info("Shutting down prescription worker")
        finally:
            self.consumer.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    PrescriptionWorker().run()
