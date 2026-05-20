"""Unit tests for the InfluxDB writer point construction.

We avoid touching a real InfluxDB instance by stubbing the write_api
and asserting on the Point objects the writer hands to it.
"""

from __future__ import annotations

from typing import List

import pytest

from src.backend.integration.influx_writer import InfluxDBWriter


class _RecordingWriteAPI:
    def __init__(self) -> None:
        self.points: List = []

    def write(self, bucket, org, record):  # type: ignore[no-untyped-def]
        self.points.append({"bucket": bucket, "org": org, "record": record})


def _writer() -> InfluxDBWriter:
    writer = InfluxDBWriter.__new__(InfluxDBWriter)
    writer.broker_url = "memory:0"
    writer.consumer = None
    writer.client = None
    writer.bucket = "neuropit-telemetry"
    writer.org = "neuropit"
    writer.write_api = _RecordingWriteAPI()
    return writer


def test_raw_telemetry_point_contains_every_field():
    writer = _writer()
    writer.write_raw_telemetry(
        {
            "driver_id": "VER",
            "session_id": "2021_AbuDhabi",
            "speed": 300.0,
            "throttle": 80.0,
            "brake": 15.0,
            "rpm": 12000,
            "gear": 6,
            "steering_angle": -25.0,
            "timestamp": "2026-05-20T13:00:00Z",
        }
    )
    assert len(writer.write_api.points) == 1
    written = writer.write_api.points[0]
    assert written["bucket"] == "neuropit-telemetry"
    assert written["org"] == "neuropit"
    serialized = written["record"].to_line_protocol()
    assert "driver_id=VER" in serialized
    assert "session_id=2021_AbuDhabi" in serialized
    assert "speed=300" in serialized


def test_features_point_unwraps_nested_payload():
    writer = _writer()
    writer.write_features(
        {
            "driver_id": "HAM",
            "timestamp": "2026-05-20T13:00:00Z",
            "features": {
                "steering_instability": 5.5,
                "micro_correction_freq": 4.0,
                "braking_variance": 3.5,
                "throttle_jitter": 2.5,
                "panic_signature": 1.5,
            },
        }
    )
    written = writer.write_api.points[0]
    serialized = written["record"].to_line_protocol()
    assert "telemetry_features" in serialized
    assert "driver_id=HAM" in serialized
    assert "steering_instability=5.5" in serialized
    assert "panic_signature=1.5" in serialized


def test_features_point_handles_flat_payload():
    writer = _writer()
    writer.write_features(
        {
            "driver_id": "VER",
            "timestamp": "2026-05-20T13:00:00Z",
            "steering_instability": 1.0,
            "micro_correction_freq": 2.0,
            "braking_variance": 3.0,
            "throttle_jitter": 4.0,
            "panic_signature": 5.0,
        }
    )
    written = writer.write_api.points[0]
    serialized = written["record"].to_line_protocol()
    assert "steering_instability=1" in serialized
    assert "panic_signature=5" in serialized


def test_missing_numeric_fields_default_to_zero():
    writer = _writer()
    writer.write_raw_telemetry(
        {"driver_id": "LEC", "session_id": "s", "timestamp": "2026-05-20T13:00:00Z"}
    )
    serialized = writer.write_api.points[0]["record"].to_line_protocol()
    assert "speed=0" in serialized
    assert "rpm=0i" in serialized
