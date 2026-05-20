"""Predictive Failure Engine.

Subscribes to the cognitive state stream and projects the probability of a
small set of race critical failures across the four prediction horizons
listed in the PRD (five seconds, one lap, three laps, full race). The V1
implementation uses interpretable probability functions rather than a trained
sequence model. The contract is honest about that. Phase 3 of the long term
roadmap swaps these functions for learned models on the same feature inputs.

The engine publishes a `failure_forecast` event per evaluation to the
`anomaly-events` topic. The dashboard renders the highest priority forecast
as the amber or red banner on the right hand side of Mission Control.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict, deque
from typing import Dict, Optional

from confluent_kafka import Consumer, Producer

from src.backend.common import audit
from src.backend.common import weights
from src.backend.config import get_settings

logger = logging.getLogger(__name__)


HORIZONS = ("5s", "1lap", "3laps", "full_race")


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _moving_average(buffer: deque) -> float:
    return sum(buffer) / len(buffer) if buffer else 0.0


class PredictiveFailureEngine:
    """Forecasts race critical failures from the cognitive state stream."""

    BUFFER_LENGTH = 60

    def __init__(self, broker_url: Optional[str] = None):
        settings = get_settings()
        self.broker_url = broker_url or settings.kafka_broker_url

        self.consumer = Consumer(
            {
                "bootstrap.servers": self.broker_url,
                "group.id": "predictive_failure_group",
                "auto.offset.reset": "latest",
            }
        )
        self.producer = Producer({"bootstrap.servers": self.broker_url})
        self.consumer.subscribe(["cognitive-state-inference"])

        self.history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=self.BUFFER_LENGTH))

    def forecast(self, state: dict) -> dict:
        """Build the forecast payload for a single cognitive state event."""
        driver_id = state.get("driver_id", "unknown")
        history = self.history[driver_id]
        history.append(state)

        stress = float(state.get("stress_score", 0.0))
        confidence = float(state.get("confidence_score", 100.0))
        fatigue = float(state.get("fatigue_score", 0.0))
        persona_state = state.get("persona_state", "Recovery")
        tunnel_vision = float(state.get("tunnel_vision_prob", 0.0)) / 100.0

        stress_recent = _moving_average(deque((float(s.get("stress_score", 0.0)) for s in history), maxlen=self.BUFFER_LENGTH))

        fw = weights.FAILURE
        stress_n = stress / 100.0
        confidence_n = confidence / 100.0
        inv_confidence = 1.0 - confidence_n
        fatigue_n = fatigue / 100.0
        stress_recent_n = stress_recent / 100.0

        crash_likelihood = _clamp(
            fw.crash_tunnel * tunnel_vision
            + fw.crash_stress * stress_n
            + fw.crash_inv_confidence * inv_confidence
        )
        lock_up_probability = _clamp(
            fw.lockup_stress * stress_n
            + fw.lockup_inv_confidence * inv_confidence
        )
        spin_probability = _clamp(
            fw.spin_inv_confidence * inv_confidence
            + fw.spin_stress * stress_n
            + fw.spin_panic_persona * (1.0 if persona_state == "Panic" else 0.0)
        )
        overtake_persona_term = (
            1.0
            if persona_state in {"Defensive", "Fatigue"}
            else fw.overtake_default_persona_term
        )
        failed_overtake_probability = _clamp(
            fw.overtake_inv_confidence * inv_confidence
            + fw.overtake_defensive_fatigue_persona * overtake_persona_term
        )
        concentration_collapse = _clamp(
            fw.collapse_fatigue * fatigue_n
            + fw.collapse_stress_recent * stress_recent_n
            + fw.collapse_fatigue_persona * (1.0 if persona_state == "Fatigue" else 0.0)
        )
        strategic_noncompliance = _clamp(
            fw.noncompliance_aggressive_persona * (1.0 if persona_state == "Aggressive" else 0.0)
            + fw.noncompliance_stress * stress_n
            + fw.noncompliance_inv_confidence * inv_confidence
        )

        horizon_weights = {
            "5s": fw.horizon_5s,
            "1lap": fw.horizon_1lap,
            "3laps": fw.horizon_3laps,
            "full_race": fw.horizon_full_race,
        }
        forecasts = {}
        for horizon in HORIZONS:
            horizon_weight = horizon_weights[horizon]
            forecasts[horizon] = {
                "crash_likelihood": round(crash_likelihood * horizon_weight, 4),
                "lock_up_probability": round(lock_up_probability * horizon_weight, 4),
                "spin_probability": round(spin_probability * horizon_weight, 4),
                "failed_overtake_probability": round(failed_overtake_probability * horizon_weight, 4),
                "concentration_collapse": round(concentration_collapse * horizon_weight, 4),
                "strategic_noncompliance": round(strategic_noncompliance * horizon_weight, 4),
            }

        return {
            "kind": "failure_forecast",
            "driver_id": driver_id,
            "timestamp": state.get("timestamp"),
            "source_persona": persona_state,
            "source_confidence_band": state.get("confidence_band"),
            "horizons": forecasts,
        }

    def run(self) -> None:
        logger.info("Predictive failure engine running on broker %s", self.broker_url)
        try:
            while True:
                msg = self.consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    logger.error("Consumer error: %s", msg.error())
                    continue

                state = json.loads(msg.value().decode("utf-8"))
                payload = self.forecast(state)

                self.producer.produce(
                    "anomaly-events",
                    key=payload["driver_id"].encode("utf-8"),
                    value=json.dumps(payload).encode("utf-8"),
                )
                self.producer.poll(0)
                audit.append(payload)

        except KeyboardInterrupt:
            logger.info("Shutting down predictive failure engine")
        finally:
            self.consumer.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    PredictiveFailureEngine().run()
