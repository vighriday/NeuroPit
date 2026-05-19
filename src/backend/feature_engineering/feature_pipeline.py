"""Feature pipeline.

Subscribes to the raw telemetry topic, maintains a per driver sliding window,
runs the signal processor on every Nth frame, and republishes the engineered
feature window to the telemetry features topic. This is the bridge between
raw car physics and the cognitive layer.
"""

from __future__ import annotations

import json
import logging
import signal
from collections import defaultdict, deque
from typing import Dict, Optional

from confluent_kafka import Consumer, KafkaError, Producer
from pydantic import ValidationError

from src.backend.config import get_settings
from src.backend.feature_engineering.signal_processor import SignalProcessor
from src.backend.ingestion.models import TelemetryFrame

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

IN_TOPIC = "incoming-telemetry-raw"
OUT_TOPIC = "telemetry-features"

WINDOW_SIZE = 10
PROCESSING_STEP = 5


class FeaturePipeline:
    def __init__(self, broker_url: Optional[str] = None):
        settings = get_settings()
        self.broker_url = broker_url or settings.kafka_broker_url

        self.consumer = Consumer(
            {
                "bootstrap.servers": self.broker_url,
                "group.id": "feature-pipeline-group",
                "auto.offset.reset": "latest",
            }
        )
        self.producer = Producer({"bootstrap.servers": self.broker_url})

        self.signal_processor = SignalProcessor(sample_rate_hz=10.0)
        self.driver_windows: Dict[str, deque] = defaultdict(lambda: deque(maxlen=WINDOW_SIZE))
        self.driver_counters: Dict[str, int] = defaultdict(int)
        self.running = True

    def _delivery_report(self, err, msg):
        if err is not None:
            logger.error("Message delivery failed: %s", err)

    def shutdown(self, sig, frame):
        logger.info("Shutting down feature pipeline")
        self.running = False

    def run(self) -> None:
        self.consumer.subscribe([IN_TOPIC])
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

        logger.info("Feature pipeline started on broker %s", self.broker_url)
        try:
            while self.running:
                msg = self.consumer.poll(timeout=0.1)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    logger.error("Consumer error: %s", msg.error())
                    break

                try:
                    data = json.loads(msg.value().decode("utf-8"))
                    frame = TelemetryFrame(**data)
                except json.JSONDecodeError as decode_err:
                    logger.error("Failed to decode message JSON: %s", decode_err)
                    continue
                except ValidationError as val_err:
                    logger.error("Validation error for incoming frame: %s", val_err)
                    continue

                driver_id = frame.driver_id
                window = self.driver_windows[driver_id]
                window.append(frame)
                self.driver_counters[driver_id] += 1

                if self.driver_counters[driver_id] >= PROCESSING_STEP:
                    features = self.signal_processor.process_window(list(window))
                    feature_msg = {
                        "timestamp": frame.timestamp.isoformat(),
                        "driver_id": driver_id,
                        "session_id": frame.session_id,
                        "features": features,
                    }
                    try:
                        self.producer.produce(
                            OUT_TOPIC,
                            key=driver_id.encode("utf-8"),
                            value=json.dumps(feature_msg).encode("utf-8"),
                            callback=self._delivery_report,
                        )
                        self.producer.poll(0)
                    except Exception as exc:
                        logger.error("Failed to produce message: %s", exc)

                    self.driver_counters[driver_id] = 0

        except KeyboardInterrupt:
            pass
        finally:
            self.producer.flush()
            self.consumer.close()


if __name__ == "__main__":
    FeaturePipeline().run()
