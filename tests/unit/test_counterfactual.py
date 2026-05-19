"""Unit tests for the counterfactual simulation engine."""

from __future__ import annotations

import pytest

from src.backend.simulation.counterfactual import SCENARIOS, run_all, run_scenario
from src.backend.simulation.ghost_lap import LapCognitiveSummary


def _summary() -> LapCognitiveSummary:
    return LapCognitiveSummary(
        lap_number=14,
        driver_id="HAM",
        actual_lap_time_s=93.4,
        average_stress=70.0,
        average_fatigue=55.0,
        panic_events=1,
    )


def test_unknown_scenario_raises():
    with pytest.raises(ValueError):
        run_scenario("teleport_to_finish_line", _summary())


def test_every_documented_scenario_runs():
    results = run_all(_summary())
    assert {r.scenario for r in results} == set(SCENARIOS)


def test_lower_fatigue_recovers_time():
    result = run_scenario("lower_fatigue", _summary())
    assert result.lap_delta_s <= 0.0


def test_stable_emotional_state_zeroes_panic():
    result = run_scenario("stable_emotional_state", _summary())
    assert "panic_events" in result.adjustments
    assert result.adjustments["panic_events"] == 0


def test_results_have_rationale_strings():
    for result in run_all(_summary()):
        assert isinstance(result.rationale, str)
        assert len(result.rationale) > 0
