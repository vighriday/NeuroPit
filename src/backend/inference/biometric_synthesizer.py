"""Biometric synthesiser.

Produces telemetry conditioned heart rate, HRV, and respiration estimates.
This module never emits a value without tagging it as synthetic so nothing
downstream can confuse it with real wearable data. The PRD calls these
"telemetry conditioned synthetic biometrics" and that label travels with
every payload.

In line with the PRD privacy requirements, the raw heart rate and HRV
values are also encrypted at rest using the project Fernet helper. The
encrypted payload is published alongside the plaintext numbers so the
cognitive engine continues to work without ceremony, but a downstream
persistence layer can choose to drop the plaintext fields when storing
biometric data to disk.
"""

from __future__ import annotations

import json
import logging
import random
from typing import Optional

from confluent_kafka import Consumer, Producer

from src.backend.config import get_settings
from src.backend.security.crypto import encrypt

logger = logging.getLogger(__name__)


class BiometricSynthesizer:
    def __init__(self, broker_url: Optional[str] = None):
        settings = get_settings()
        self.broker_url = broker_url or settings.kafka_broker_url

        self.consumer = Consumer(
            {
                "bootstrap.servers": self.broker_url,
                "group.id": "biometric_synth_group",
                "auto.offset.reset": "earliest",
            }
        )
        self.producer = Producer({"bootstrap.servers": self.broker_url})
        self.consumer.subscribe(["telemetry-features"])
        self.driver_state: dict = {}

    def synthesize(self, driver_id: str, features: dict) -> dict:
        if driver_id not in self.driver_state:
            self.driver_state[driver_id] = {
                "base_hr": 140.0,
                "base_hrv": 50.0,
                "current_hr": 140.0,
                "current_hrv": 50.0,
            }

        state = self.driver_state[driver_id]

        f_nested = features.get("features", features)
        instability = float(f_nested.get("steering_instability", 0.0))
        throttle_commitment = float(f_nested.get("throttle_commitment", 0.0))
        panic = float(f_nested.get("panic_oscillation", f_nested.get("panic_signature", 0.0)))

        hr_delta = (panic * 1.5) + (throttle_commitment * 0.2) - 0.2
        state["current_hr"] = min(195.0, max(110.0, state["current_hr"] + hr_delta))

        hrv_delta = (instability * -2.0) + random.uniform(-0.5, 0.5)
        if hr_delta <= 0:
            hrv_delta += 0.5
        state["current_hrv"] = min(80.0, max(15.0, state["current_hrv"] + hrv_delta))

        respiration = float(20.0 + (state["current_hr"] - 140) * 0.2)

        encrypted_payload = encrypt(
            json.dumps(
                {
                    "synthetic_hr": state["current_hr"],
                    "synthetic_hrv": state["current_hrv"],
                    "respiration_rate": respiration,
                }
            )
        )

        return {
            "driver_id": driver_id,
            "timestamp": features.get("timestamp"),
            "synthetic_hr": float(state["current_hr"]),
            "synthetic_hrv": float(state["current_hrv"]),
            "respiration_rate": respiration,
            "source": "synthetic",
            "encrypted_payload": encrypted_payload,
        }

    def run(self) -> None:
        logger.info("Biometric synthesiser listening on broker %s", self.broker_url)
        try:
            while True:
                msg = self.consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    logger.error("Consumer error: %s", msg.error())
                    continue

                features = json.loads(msg.value().decode("utf-8"))
                driver_id = features.get("driver_id")

                biometrics = self.synthesize(driver_id, features)
                self.producer.produce(
                    "biometrics-enriched",
                    key=driver_id.encode("utf-8"),
                    value=json.dumps(biometrics).encode("utf-8"),
                )
                self.producer.poll(0)

        except KeyboardInterrupt:
            logger.info("Shutting down biometric synthesiser")
        finally:
            self.consumer.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    BiometricSynthesizer().run()
