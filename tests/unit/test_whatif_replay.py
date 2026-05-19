"""Unit tests for the audit log driven What If Replay engine."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import date

import pytest

from src.backend.whatif.replay import (
    apply_mutations,
    build_rationale,
    load_audit_window,
    replay_trajectory,
    summarise_trajectory,
)


def _row(timestamp: str, **overrides):
    base = {
        "kind": "cognitive_evaluation",
        "driver_id": "VER",
        "timestamp": timestamp,
        "state": {
            "driver_id": "VER",
            "timestamp": timestamp,
            "stress_score": 60.0,
            "confidence_score": 70.0,
            "fatigue_score": 30.0,
            "cognitive_load_score": 45.0,
            "panic_probability": 12.0,
            "persona_state": "Recovery",
            "confidence_band": "high",
        },
        "inputs": {
            "features": {
                "driver_id": "VER",
                "timestamp": timestamp,
                "steering_instability": 4.0,
                "panic_oscillation": 6.0,
                "throttle_commitment": 78.0,
                "braking_hesitation": 4.0,
                "micro_correction_freq": 6.0,
                "throttle_jitter": 8.0,
                "line_consistency": 70.0,
                "reaction_smoothness": 70.0,
            },
            "biometrics": {
                "driver_id": "VER",
                "timestamp": timestamp,
                "synthetic_hr": 155.0,
                "synthetic_hrv": 50.0,
                "respiration_rate": 22.0,
            },
        },
        "weights": {"version": "test"},
    }
    base["state"].update(overrides)
    return base


def test_apply_mutations_overrides_nested_field():
    row = _row("2026-05-19T12:00:00Z")
    mutated = apply_mutations(row, [{"target": "inputs.biometrics.synthetic_hr", "value": 130.0}])
    assert mutated["inputs"]["biometrics"]["synthetic_hr"] == 130.0
    # Original row untouched.
    assert row["inputs"]["biometrics"]["synthetic_hr"] == 155.0


def test_apply_mutations_rejects_unknown_path():
    row = _row("2026-05-19T12:00:00Z")
    mutated = apply_mutations(row, [{"target": "inputs.does.not.exist", "value": 1.0}])
    # Original row unchanged because target did not resolve.
    assert mutated == row


def test_apply_mutations_rejects_dangerous_paths():
    row = _row("2026-05-19T12:00:00Z")
    for bad in ("..", "inputs..biometrics", "inputs/biometrics", " inputs.biometrics"):
        mutated = apply_mutations(row, [{"target": bad, "value": 99.0}])
        assert mutated == row


def test_replay_trajectory_matches_baseline_when_no_mutations():
    rows = [_row(f"2026-05-19T12:00:0{i}Z") for i in range(3)]
    traj = replay_trajectory(rows, [])
    for point in traj:
        assert point.baseline == point.counterfactual
        for value in point.delta.values():
            assert value == 0.0


def test_replay_trajectory_diverges_under_mutation():
    rows = [_row(f"2026-05-19T12:00:0{i}Z") for i in range(3)]
    traj = replay_trajectory(rows, [{"target": "inputs.biometrics.synthetic_hr", "value": 110.0}])
    # Lowering HR below the stress baseline should drop stress to zero
    # in the counterfactual.
    assert all(point.counterfactual["stress_score"] < point.baseline["stress_score"] for point in traj)


def test_summarise_trajectory_picks_largest_delta():
    rows = [_row(f"2026-05-19T12:00:0{i}Z") for i in range(3)]
    traj = replay_trajectory(rows, [{"target": "inputs.biometrics.synthetic_hr", "value": 110.0}])
    summary = summarise_trajectory(traj)
    assert summary["biggest_delta_field"] == "stress_score"
    assert summary["biggest_delta_value"] < 0.0


def test_build_rationale_with_no_mutations_says_no_divergence():
    rationale = build_rationale(summarise_trajectory([]), [])
    assert "no mutations" in rationale.lower()


def test_load_audit_window_reads_only_target_driver(tmp_path):
    audit_file = tmp_path / "cognitive-2026-05-19.jsonl"
    with audit_file.open("w", encoding="utf-8") as fh:
        for i in range(3):
            row = _row(f"2026-05-19T12:00:0{i}Z")
            fh.write(json.dumps(row) + "\n")
        ham_row = _row("2026-05-19T12:00:99Z")
        ham_row["driver_id"] = "HAM"
        ham_row["state"]["driver_id"] = "HAM"
        fh.write(json.dumps(ham_row) + "\n")
        fh.write(json.dumps({"kind": "explanation", "driver_id": "VER"}) + "\n")

    rows = load_audit_window("VER", 10, audit_path=str(audit_file))
    assert len(rows) == 3
    assert all(row["driver_id"] == "VER" for row in rows)
