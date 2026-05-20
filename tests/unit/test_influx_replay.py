"""Unit tests for the InfluxDB replay helpers.

The replay CLI talks to a live InfluxDB at runtime, but the query
builder and the row-to-frame mapper are pure functions that we can
pin in isolation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from src.backend.integration.influx_replay import _build_query, _row_to_frame


def _row(values: dict, time_value=None) -> SimpleNamespace:
    record = SimpleNamespace(values=values)
    record.get_time = lambda: time_value if time_value is not None else datetime.now(timezone.utc)
    return record


def test_build_query_filters_by_session_and_driver(monkeypatch):
    monkeypatch.setenv("INFLUXDB_BUCKET", "neuropit-telemetry")
    from src.backend.config import get_settings

    get_settings.cache_clear()
    query = _build_query("2021_AbuDhabi", "VER", 12)

    assert 'from(bucket: "neuropit-telemetry")' in query
    assert "range(start: -12h)" in query
    assert 'r._measurement == "raw_telemetry"' in query
    assert 'r.session_id == "2021_AbuDhabi"' in query
    assert 'r.driver_id == "VER"' in query
    assert "pivot" in query


def test_build_query_minimum_hours_clamps_to_one(monkeypatch):
    monkeypatch.setenv("INFLUXDB_BUCKET", "neuropit-telemetry")
    from src.backend.config import get_settings

    get_settings.cache_clear()
    query = _build_query(None, None, 0)
    assert "range(start: -1h)" in query


def test_row_to_frame_uses_row_tags_first():
    row = _row(
        {
            "driver_id": "HAM",
            "session_id": "2021_AbuDhabi",
            "speed": 290.5,
            "rpm": 11500,
            "gear": 7,
            "throttle": 92.0,
            "brake": 5.0,
            "steering_angle": -12.0,
        },
        time_value=datetime(2026, 5, 20, 13, 0, 0, tzinfo=timezone.utc),
    )
    frame = _row_to_frame(row, "VER", "fallback")
    assert frame["driver_id"] == "HAM"
    assert frame["session_id"] == "2021_AbuDhabi"
    assert frame["speed"] == 290.5
    assert frame["rpm"] == 11500
    assert frame["gear"] == 7
    assert frame["status"] == "Replay"
    assert frame["timestamp"].startswith("2026-05-20T13:00:00")


def test_row_to_frame_falls_back_to_default_tags():
    row = _row({}, time_value=datetime(2026, 5, 20, 13, 0, 0, tzinfo=timezone.utc))
    frame = _row_to_frame(row, "VER", "fallback")
    assert frame["driver_id"] == "VER"
    assert frame["session_id"] == "fallback"
    assert frame["speed"] == 0.0
    assert frame["rpm"] == 0
    assert frame["status"] == "Replay"


def test_row_to_frame_handles_none_numeric_fields():
    row = _row({"speed": None, "rpm": None, "throttle": None}, time_value=datetime(2026, 5, 20, 13, 0, 0, tzinfo=timezone.utc))
    frame = _row_to_frame(row, "VER", "replay")
    assert frame["speed"] == 0.0
    assert frame["rpm"] == 0
    assert frame["throttle"] == 0.0
