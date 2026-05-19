"""Unit tests for Ghost Lap AI."""

from __future__ import annotations

from src.backend.simulation.ghost_lap import LapCognitiveSummary, attribute_lost_time, attribute_lap_series


def _summary(**overrides) -> LapCognitiveSummary:
    base = dict(
        lap_number=1,
        driver_id="VER",
        actual_lap_time_s=92.0,
        average_stress=40.0,
        average_fatigue=20.0,
        panic_events=0,
    )
    base.update(overrides)
    return LapCognitiveSummary(**base)


def test_clean_lap_has_minimal_lost_time():
    result = attribute_lost_time(_summary(average_stress=5.0, average_fatigue=5.0))
    assert result.lost_time_s < 0.2
    assert result.ghost_lap_time_s <= result.actual_lap_time_s


def test_panic_events_increase_lost_time():
    quiet = attribute_lost_time(_summary())
    noisy = attribute_lost_time(_summary(panic_events=3))
    assert noisy.lost_time_s > quiet.lost_time_s


def test_lost_time_caps_at_ceiling():
    crazy = attribute_lost_time(_summary(average_stress=100.0, average_fatigue=100.0, panic_events=10))
    assert crazy.lost_time_s <= 3.0


def test_lap_series_keeps_order():
    summaries = [_summary(lap_number=i, actual_lap_time_s=90.0 + i) for i in range(5)]
    results = attribute_lap_series(summaries)
    assert [r.lap_number for r in results] == list(range(5))
