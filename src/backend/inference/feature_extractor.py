"""Lightweight feature extractor.

Mirrors a subset of the signal processor for the inference path. Keeps a per
driver three second sliding window and emits a flat behavioural feature
record. The output schema is deliberately stable so the biometric synthesiser
and the cognitive engine can rely on the field names.
"""

from __future__ import annotations

import json
import logging
from collections import deque
from typing import Dict, Optional

import numpy as np
from confluent_kafka import Consumer, Producer

from src.backend.config import get_settings

logger = logging.getLogger(__name__)


class FeatureExtractor:
    def __init__(self, broker_url: Optional[str] = None):
        settings = get_settings()
        self.broker_url = broker_url or settings.kafka_broker_url

        self.consumer = Consumer(
            {
                "bootstrap.servers": self.broker_url,
                "group.id": "feature_extractor_group",
                "auto.offset.reset": "earliest",
            }
        )
        self.producer = Producer({"bootstrap.servers": self.broker_url})
        self.consumer.subscribe(["incoming-telemetry-raw"])

        self.history: Dict[str, Dict[str, deque]] = {}

    def extract_features(self, driver_id: str, current_frame: dict) -> Optional[dict]:
        if driver_id not in self.history:
            self.history[driver_id] = {
                "steering": deque(maxlen=30),
                "throttle": deque(maxlen=30),
                "brake": deque(maxlen=30),
                "speed": deque(maxlen=30),
                "timestamps": deque(maxlen=30),
            }

        hist = self.history[driver_id]
        hist["steering"].append(current_frame.get("steering_angle", 0.0))
        hist["throttle"].append(current_frame.get("throttle", 0.0))
        hist["brake"].append(current_frame.get("brake", 0.0))
        hist["speed"].append(current_frame.get("speed", 0.0))

        if len(hist["steering"]) < 10:
            return None

        steering_arr = np.array(hist["steering"])
        steering_diff = np.diff(steering_arr)
        brake_arr = np.array(hist["brake"])
        throttle_arr = np.array(hist["throttle"])
        throttle_diff = np.diff(throttle_arr)
        speed_arr = np.array(hist["speed"])
        speed_diff = np.diff(speed_arr)
        rapid_decel = float(np.sum(speed_diff < -15.0))

        features = {
            "driver_id": driver_id,
            "timestamp": current_frame.get("timestamp"),
            "steering_instability": float(np.std(steering_diff)),
            "micro_correction_freq": float(np.sum(np.abs(steering_diff) > 2.0)),
            "braking_variance": float(np.std(brake_arr)),
            "throttle_jitter": float(np.sum(np.abs(throttle_diff[throttle_diff < 0]))),
            "panic_signature": 0.0,
        }
        features["panic_signature"] = float(
            (features["steering_instability"] * 0.6) + (rapid_decel * 0.4)
        )
        return features

    def run(self) -> None:
        logger.info("Feature extractor listening on broker %s", self.broker_url)
        try:
            while True:
                msg = self.consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    logger.error("Consumer error: %s", msg.error())
                    continue

                raw_data = json.loads(msg.value().decode("utf-8"))
                driver_id = raw_data.get("driver_id")

                features = self.extract_features(driver_id, raw_data)
                if features:
                    self.producer.produce(
                        "telemetry-features",
                        key=driver_id.encode("utf-8"),
                        value=json.dumps(features).encode("utf-8"),
                    )
                    self.producer.poll(0)

        except KeyboardInterrupt:
            logger.info("Shutting down feature extractor")
        finally:
            self.consumer.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    FeatureExtractor().run()
