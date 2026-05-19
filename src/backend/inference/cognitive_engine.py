"""Probabilistic Cognitive Inference Engine.

Joins the per driver feature stream with the synthetic biometric stream and
emits a cognitive twin state for every processing step. Every output carries
a confidence band and a snapshot of the active weights so the dashboard, the
explainability worker, and the audit log can each tell the same story about
how a given number was produced.

The maths is documented in `docs/COGNITIVE_METHODOLOGY.md`. The topic shapes
are documented in `docs/EVENT_TAXONOMY.md`. If either document disagrees with
the code, the documents win.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from confluent_kafka import Consumer, Producer
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from src.backend.common import audit, persona, uncertainty, weights
from src.backend.config import get_settings

logger = logging.getLogger(__name__)


def _clamp_0_100(value: float) -> float:
    return float(max(0.0, min(100.0, value)))


class CognitiveInferenceEngine:
    def __init__(self, broker_url: Optional[str] = None):
        settings = get_settings()
        self.broker_url = broker_url or settings.kafka_broker_url

        self.consumer = Consumer(
            {
                "bootstrap.servers": self.broker_url,
                "group.id": "cognitive_engine_group",
                "auto.offset.reset": "earliest",
            }
        )
        self.producer = Producer({"bootstrap.servers": self.broker_url})
        self.consumer.subscribe(["telemetry-features", "biometrics-enriched"])

        self.state_cache: dict = {}
        self.weights_snapshot = weights.snapshot()

        self.influx_client = InfluxDBClient(
            url=settings.influxdb_url,
            token=settings.influxdb_token,
            org=settings.influxdb_org,
        )
        self.influx_bucket = settings.influxdb_bucket
        self.influx_org = settings.influxdb_org
        self.write_api = self.influx_client.write_api(write_options=SYNCHRONOUS)

    def process_message(self, topic: str, data: dict) -> None:
        driver_id = data.get("driver_id")
        timestamp = data.get("timestamp")
        if not driver_id:
            return

        cache = self.state_cache.setdefault(
            driver_id,
            {"features": {}, "biometrics": {}, "cumulative_fatigue": 0.0},
        )

        if topic == "telemetry-features":
            cache["features"] = data
        elif topic == "biometrics-enriched":
            cache["biometrics"] = data

        if cache["features"] and cache["biometrics"]:
            self.evaluate(driver_id, timestamp, cache)

    def evaluate(self, driver_id: str, timestamp: str, cache: dict) -> None:
        feature_msg = cache["features"]
        features = feature_msg.get("features", feature_msg)
        biometrics = cache["biometrics"]

        w = weights.STRESS
        c = weights.CONFIDENCE
        f = weights.FATIGUE

        steering_term = min(float(features.get("steering_instability", 0.0)) * w.steering_gain, 100.0)
        hr_value = float(biometrics.get("synthetic_hr", w.hr_baseline))
        hr_term = max(0.0, hr_value - w.hr_baseline) * w.hr_gain
        panic_term = float(features.get("panic_oscillation", features.get("panic_signature", 0.0)))

        stress_score = _clamp_0_100(
            steering_term * w.steering
            + hr_term * w.heart_rate
            + panic_term * w.panic
        )

        throttle_commitment = float(features.get("throttle_commitment", 0.0))
        throttle_term = min(throttle_commitment * c.throttle_gain, 100.0)
        hesitation_pen = float(features.get("braking_hesitation", 0.0)) * c.hesitation_penalty
        confidence_score = _clamp_0_100(
            100.0 - ((100.0 - throttle_term) * c.throttle_term_weight + hesitation_pen)
        )

        cache["cumulative_fatigue"] += (
            stress_score * f.stress_term
            + float(features.get("steering_instability", 0.0)) * f.steering_term
        )
        fatigue_score = min(100.0, cache["cumulative_fatigue"])

        persona_state = persona.classify(
            stress=stress_score,
            confidence=confidence_score,
            fatigue=fatigue_score,
            panic_oscillation=panic_term,
            throttle_commitment=throttle_commitment,
        )

        trust = uncertainty.evaluate(
            frame={
                "steering_instability": features.get("steering_instability"),
                "panic_oscillation": features.get("panic_oscillation"),
                "throttle_commitment": features.get("throttle_commitment"),
                "braking_hesitation": features.get("braking_hesitation"),
                "synthetic_hr": biometrics.get("synthetic_hr"),
                "synthetic_hrv": biometrics.get("synthetic_hrv"),
            },
            signal_directions=[
                steering_term,
                hr_term,
                panic_term,
                -hesitation_pen,
            ],
        )

        tunnel_vision = 100.0 if stress_score > weights.PERSONA.panic_stress else 0.0

        cognitive_state = {
            "driver_id": driver_id,
            "timestamp": timestamp,
            "stress_score": stress_score,
            "confidence_score": confidence_score,
            "fatigue_score": fatigue_score,
            "tunnel_vision_prob": tunnel_vision,
            "persona_state": persona_state,
            "confidence_band": trust.band,
            "trust": trust.to_dict(),
            "weights_version": self.weights_snapshot["version"],
            "explainability_pending": True,
        }

        self.producer.produce(
            "cognitive-state-inference",
            key=driver_id.encode("utf-8"),
            value=json.dumps(cognitive_state).encode("utf-8"),
        )
        self.producer.poll(0)

        self._persist_state(cognitive_state)
        self._audit(cognitive_state, features, biometrics)

    def _persist_state(self, state: dict) -> None:
        try:
            point = (
                Point("cognitive_state")
                .tag("driver_id", state["driver_id"])
                .tag("persona_state", state["persona_state"])
                .tag("confidence_band", state["confidence_band"])
                .field("stress_score", float(state["stress_score"]))
                .field("confidence_score", float(state["confidence_score"]))
                .field("fatigue_score", float(state["fatigue_score"]))
                .field("tunnel_vision_prob", float(state["tunnel_vision_prob"]))
                .time(state["timestamp"], WritePrecision.NS)
            )
            self.write_api.write(bucket=self.influx_bucket, org=self.influx_org, record=point)
        except Exception as exc:
            logger.warning("InfluxDB cognitive write failed: %s", exc)

    def _audit(self, state: dict, features: dict, biometrics: dict) -> None:
        audit.append(
            {
                "kind": "cognitive_evaluation",
                "driver_id": state["driver_id"],
                "timestamp": state["timestamp"],
                "state": state,
                "inputs": {
                    "features": features,
                    "biometrics": biometrics,
                },
                "weights": self.weights_snapshot,
            }
        )

    def run(self) -> None:
        logger.info("Cognitive engine evaluating live streams on broker %s", self.broker_url)
        try:
            while True:
                msg = self.consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    logger.error("Consumer error: %s", msg.error())
                    continue

                topic = msg.topic()
                data = json.loads(msg.value().decode("utf-8"))
                self.process_message(topic, data)

        except KeyboardInterrupt:
            logger.info("Shutting down cognitive engine")
        finally:
            self.consumer.close()
            self.influx_client.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    CognitiveInferenceEngine().run()
