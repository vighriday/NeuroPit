"""Probabilistic Cognitive Inference Engine.

This is the core of the NeuroPit Cognitive Twin Operating System. Telemetry
flows in. A probabilistic Cognitive Twin flows out. Every output carries a
confidence band and a snapshot of the active weights so the surface, the
IBM Granite explainable cognitive reasoning worker, and the audit log can
each tell the same story about how a given number was produced.

The engine emits the full nine score cognitive twin described in PRD section
fifteen: stress, cognitive load, confidence, fatigue, tunnel vision, panic
probability, attention stability, strategic reliability, and emotional
drift. The maths is documented in `docs/COGNITIVE_METHODOLOGY.md`. The topic
shapes are documented in `docs/EVENT_TAXONOMY.md`. If either document
disagrees with the code, the documents win.
"""

from __future__ import annotations

import json
import logging
from collections import deque
from typing import Optional

from confluent_kafka import Consumer, Producer
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from src.backend.common import audit, persona, uncertainty, weights
from src.backend.config import get_settings

logger = logging.getLogger(__name__)


def _clamp_0_100(value: float) -> float:
    return float(max(0.0, min(100.0, value)))


def _inv(value: float) -> float:
    """Invert a zero to one hundred score to its complement."""
    return _clamp_0_100(100.0 - value)


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
            {
                "features": {},
                "biometrics": {},
                "cumulative_fatigue": 0.0,
                "confidence_history": deque(maxlen=weights.EMOTIONAL_DRIFT.window_size),
            },
        )

        if topic == "telemetry-features":
            cache["features"] = data
        elif topic == "biometrics-enriched":
            cache["biometrics"] = data

        if cache["features"] and cache["biometrics"]:
            self.evaluate(driver_id, timestamp, cache)

    def evaluate(self, driver_id: str, timestamp: str, cache: dict) -> dict:
        feature_msg = cache["features"]
        features = feature_msg.get("features", feature_msg)
        biometrics = cache["biometrics"]

        steering_instability = float(features.get("steering_instability", 0.0))
        panic_oscillation = float(features.get("panic_oscillation", features.get("panic_signature", 0.0)))
        throttle_commitment = float(features.get("throttle_commitment", 0.0))
        braking_hesitation = float(features.get("braking_hesitation", 0.0))
        micro_correction = float(features.get("micro_correction_freq", 0.0))
        throttle_jitter = float(features.get("throttle_jitter", 0.0))
        line_consistency = float(features.get("line_consistency", 50.0))
        reaction_smoothness = float(features.get("reaction_smoothness", 50.0))

        synthetic_hr = float(biometrics.get("synthetic_hr", weights.STRESS.hr_baseline))

        # Stress
        sw = weights.STRESS
        steering_term = min(steering_instability * sw.steering_gain, 100.0)
        hr_term = max(0.0, synthetic_hr - sw.hr_baseline) * sw.hr_gain
        stress_score = _clamp_0_100(
            steering_term * sw.steering
            + hr_term * sw.heart_rate
            + panic_oscillation * sw.panic
        )

        # Confidence
        cw = weights.CONFIDENCE
        throttle_term = min(throttle_commitment * cw.throttle_gain, 100.0)
        hesitation_pen = braking_hesitation * cw.hesitation_penalty
        confidence_score = _clamp_0_100(
            100.0 - ((100.0 - throttle_term) * cw.throttle_term_weight + hesitation_pen)
        )

        # Fatigue
        fw = weights.FATIGUE
        cache["cumulative_fatigue"] += (
            stress_score * fw.stress_term
            + steering_instability * fw.steering_term
        )
        fatigue_score = min(100.0, cache["cumulative_fatigue"])

        # Tunnel vision
        tunnel_vision_prob = 100.0 if stress_score > weights.PERSONA.panic_stress else 0.0

        # Cognitive load
        clw = weights.COGNITIVE_LOAD
        cognitive_load_score = _clamp_0_100(
            min(micro_correction * 5.0, 100.0) * clw.micro_correction
            + min(throttle_jitter * 0.5, 100.0) * clw.throttle_jitter
            + min(panic_oscillation * 3.0, 100.0) * clw.panic
            + stress_score * clw.stress
        )

        # Attention stability
        aw = weights.ATTENTION
        attention_stability = _clamp_0_100(
            confidence_score * aw.confidence
            + _inv(stress_score) * aw.inv_stress
            + _inv(min(steering_instability * sw.steering_gain, 100.0)) * aw.inv_steering_instability
            + _inv(min(micro_correction * 5.0, 100.0)) * aw.inv_micro_correction
        )

        # Strategic reliability
        srw = weights.STRATEGIC
        strategic_reliability = _clamp_0_100(
            confidence_score * srw.confidence
            + attention_stability * srw.attention
            + _inv(fatigue_score) * srw.inv_fatigue
            + _inv(min(panic_oscillation * 3.0, 100.0)) * srw.inv_panic
        )

        # Panic probability
        pw = weights.PANIC
        panic_probability = _clamp_0_100(
            min(panic_oscillation * pw.panic_oscillation_gain, 100.0)
            * (1.0 - pw.stress_term - pw.tunnel_vision_term)
            + stress_score * pw.stress_term
            + tunnel_vision_prob * pw.tunnel_vision_term
        )

        # Emotional drift
        cache["confidence_history"].append(confidence_score)
        history = cache["confidence_history"]
        if len(history) >= 5:
            baseline = sum(history) / len(history)
            drift_raw = abs(confidence_score - baseline) * weights.EMOTIONAL_DRIFT.drift_gain
            emotional_drift = _clamp_0_100(drift_raw)
        else:
            emotional_drift = 0.0

        persona_state = persona.classify(
            stress=stress_score,
            confidence=confidence_score,
            fatigue=fatigue_score,
            panic_oscillation=panic_oscillation,
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
                panic_oscillation,
                -hesitation_pen,
            ],
        )

        cognitive_state = {
            "driver_id": driver_id,
            "timestamp": timestamp,
            "stress_score": stress_score,
            "confidence_score": confidence_score,
            "fatigue_score": fatigue_score,
            "cognitive_load_score": cognitive_load_score,
            "attention_stability": attention_stability,
            "strategic_reliability": strategic_reliability,
            "panic_probability": panic_probability,
            "emotional_drift_score": emotional_drift,
            "tunnel_vision_prob": tunnel_vision_prob,
            "persona_state": persona_state,
            "confidence_band": trust.band,
            "trust": trust.to_dict(),
            "weights_version": self.weights_snapshot["version"],
            "explainability_pending": True,
            "context": {
                "line_consistency": line_consistency,
                "reaction_smoothness": reaction_smoothness,
            },
        }

        self.producer.produce(
            "cognitive-state-inference",
            key=driver_id.encode("utf-8"),
            value=json.dumps(cognitive_state).encode("utf-8"),
        )
        self.producer.poll(0)

        self._persist_state(cognitive_state)
        self._audit(cognitive_state, features, biometrics)
        return cognitive_state

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
                .field("cognitive_load_score", float(state["cognitive_load_score"]))
                .field("attention_stability", float(state["attention_stability"]))
                .field("strategic_reliability", float(state["strategic_reliability"]))
                .field("panic_probability", float(state["panic_probability"]))
                .field("emotional_drift_score", float(state["emotional_drift_score"]))
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
