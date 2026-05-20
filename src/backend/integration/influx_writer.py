"""InfluxDB writer.

Persists raw telemetry and engineered features into the time series store.
The cognitive engine writes its own state separately so this module stays
focused on the upstream signals.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from confluent_kafka import Consumer
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from src.backend.config import get_settings

logger = logging.getLogger(__name__)


class InfluxDBWriter:
    def __init__(self, kafka_broker: Optional[str] = None):
        settings = get_settings()
        self.broker_url = kafka_broker or settings.kafka_broker_url
        self.bucket = settings.influxdb_bucket
        self.org = settings.influxdb_org

        self.client = InfluxDBClient(
            url=settings.influxdb_url,
            token=settings.influxdb_token,
            org=self.org,
        )
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)

        self.consumer = Consumer(
            {
                "bootstrap.servers": self.broker_url,
                "group.id": "influx_writer_group",
                "auto.offset.reset": "earliest",
            }
        )
        self.consumer.subscribe(["incoming-telemetry-raw", "telemetry-features"])

    def write_raw_telemetry(self, data: dict) -> None:
        point = (
            Point("raw_telemetry")
            .tag("driver_id", data.get("driver_id"))
            .tag("session_id", data.get("session_id"))
            .field("speed", float(data.get("speed", 0.0)))
            .field("throttle", float(data.get("throttle", 0.0)))
            .field("brake", float(data.get("brake", 0.0)))
            .field("rpm", int(data.get("rpm", 0)))
            .field("gear", int(data.get("gear", 0)))
            .field("steering_angle", float(data.get("steering_angle", 0.0)))
            .time(data.get("timestamp"), WritePrecision.NS)
        )
        self.write_api.write(bucket=self.bucket, org=self.org, record=point)

    def write_features(self, data: dict) -> None:
        flat = data.get("features", data)
        point = (
            Point("telemetry_features")
            .tag("driver_id", data.get("driver_id"))
            .field("steering_instability", float(flat.get("steering_instability", 0.0)))
            .field("micro_correction_freq", float(flat.get("micro_correction_freq", 0.0)))
            .field("braking_variance", float(flat.get("braking_variance", 0.0)))
            .field("throttle_jitter", float(flat.get("throttle_jitter", 0.0)))
            .field("panic_signature", float(flat.get("panic_signature", 0.0)))
            .time(data.get("timestamp"), WritePrecision.NS)
        )
        self.write_api.write(bucket=self.bucket, org=self.org, record=point)

    def run(self) -> None:
        logger.info("InfluxDB writer listening on broker %s", self.broker_url)
        try:
            while True:
                msg = self.consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    logger.error("Consumer error: %s", msg.error())
                    continue

                topic = msg.topic()
                try:
                    data = json.loads(msg.value().decode("utf-8"))
                except Exception as exc:
                    logger.debug(
                        "Skipping malformed payload on %s: %s", topic, exc
                    )
                    continue
                try:
                    if topic == "incoming-telemetry-raw":
                        self.write_raw_telemetry(data)
                    elif topic == "telemetry-features":
                        self.write_features(data)
                except Exception as exc:
                    logger.warning("InfluxDB write failed: %s", exc)

        except KeyboardInterrupt:
            logger.info("Shutting down InfluxDB writer")
        finally:
            self.consumer.close()
            self.client.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    InfluxDBWriter().run()
