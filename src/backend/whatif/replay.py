"""Audit log driven cognitive trajectory replay.

Reads audit JSONL rows for a driver, optionally mutates the input
vector, and re runs the cognitive engine's deterministic maths over the
mutated rows. Returns a paired baseline-vs-counterfactual trajectory
plus a divergence summary the surface can render directly.

This module deliberately does NOT spin up Kafka or InfluxDB. Replay is a
pure function of the audit log. The same logic that lives in
`CognitiveInferenceEngine.evaluate` is mirrored here so that test data,
old session replays, and what if scenarios all use the same maths. If the
two ever drift the cognitive engine wins and this module must be updated.
"""

from __future__ import annotations

import json
import logging
import os
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Tuple

from src.backend.common import persona, weights
from src.backend.config import get_settings

logger = logging.getLogger(__name__)


COGNITIVE_FIELDS = (
    "stress_score",
    "confidence_score",
    "fatigue_score",
    "cognitive_load_score",
    "attention_stability",
    "strategic_reliability",
    "panic_probability",
    "emotional_drift_score",
    "tunnel_vision_prob",
)


def _resolve_audit_path(custom_path: Optional[str]) -> str:
    if custom_path:
        return custom_path
    settings = get_settings()
    return os.path.join(settings.audit_log_dir, f"cognitive-{date.today().isoformat()}.jsonl")


def load_audit_window(
    driver_id: str,
    window_seconds: int,
    audit_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return the last `window_seconds` of cognitive_evaluation rows for a driver."""
    path = _resolve_audit_path(audit_path)
    if not os.path.isfile(path):
        return []

    matched: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("kind") != "cognitive_evaluation":
                continue
            if row.get("driver_id") != driver_id:
                continue
            matched.append(row)

    if not matched:
        return []
    # Audit rows are time ordered already, take the trailing window.
    take = max(window_seconds, 1)
    return matched[-take:]


def _set_nested(target: Dict[str, Any], dotted_path: str, value: Any) -> bool:
    """Set a value inside the audit row using a dotted path.

    Returns True when the path resolved successfully. Whitespace and
    explicit array indices are rejected to keep the surface small.
    """
    if not dotted_path or any(ch.isspace() for ch in dotted_path):
        return False
    if not re.fullmatch(r"[A-Za-z0-9_.]+", dotted_path):
        return False
    parts = dotted_path.split(".")
    cursor: Any = target
    for part in parts[:-1]:
        if not isinstance(cursor, dict) or part not in cursor:
            return False
        cursor = cursor[part]
    if not isinstance(cursor, dict):
        return False
    cursor[parts[-1]] = value
    return True


def apply_mutations(row: Dict[str, Any], mutations: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    mutated = deepcopy(row)
    for mutation in mutations:
        target = str(mutation.get("target", ""))
        value = mutation.get("value")
        _set_nested(mutated, target, value)
    return mutated


def _clamp(v: float) -> float:
    return float(max(0.0, min(100.0, v)))


def _inv(v: float) -> float:
    return _clamp(100.0 - v)


def _recompute_cognitive(features: Dict[str, Any], biometrics: Dict[str, Any], history: List[float]) -> Dict[str, float]:
    """Deterministic cognitive recomputation mirroring `CognitiveInferenceEngine`.

    Kept here so what if replay does not need to boot Kafka or the engine
    class. If the engine maths changes, update both files in the same
    commit. There is a unit test that pins this contract.
    """
    f = features.get("features", features) if isinstance(features, dict) else {}

    steering_instability = float(f.get("steering_instability", 0.0))
    panic_oscillation = float(f.get("panic_oscillation", f.get("panic_signature", 0.0)))
    throttle_commitment = float(f.get("throttle_commitment", 0.0))
    braking_hesitation = float(f.get("braking_hesitation", 0.0))
    micro_correction = float(f.get("micro_correction_freq", 0.0))
    throttle_jitter = float(f.get("throttle_jitter", 0.0))

    synthetic_hr = float((biometrics or {}).get("synthetic_hr", weights.STRESS.hr_baseline))

    sw = weights.STRESS
    steering_term = min(steering_instability * sw.steering_gain, 100.0)
    hr_term = max(0.0, synthetic_hr - sw.hr_baseline) * sw.hr_gain
    stress_score = _clamp(steering_term * sw.steering + hr_term * sw.heart_rate + panic_oscillation * sw.panic)

    cw = weights.CONFIDENCE
    throttle_term = min(throttle_commitment * cw.throttle_gain, 100.0)
    hesitation_pen = braking_hesitation * cw.hesitation_penalty
    confidence_score = _clamp(100.0 - ((100.0 - throttle_term) * cw.throttle_term_weight + hesitation_pen))

    fw = weights.FATIGUE
    fatigue_delta = stress_score * fw.stress_term + steering_instability * fw.steering_term
    fatigue_score = min(100.0, history[-1] if history else 0.0)
    fatigue_score = min(100.0, fatigue_score + fatigue_delta)
    history.append(fatigue_score)

    tunnel_vision_prob = 100.0 if stress_score > weights.PERSONA.panic_stress else 0.0

    clw = weights.COGNITIVE_LOAD
    cognitive_load_score = _clamp(
        min(micro_correction * 5.0, 100.0) * clw.micro_correction
        + min(throttle_jitter * 0.5, 100.0) * clw.throttle_jitter
        + min(panic_oscillation * 3.0, 100.0) * clw.panic
        + stress_score * clw.stress
    )

    aw = weights.ATTENTION
    attention_stability = _clamp(
        confidence_score * aw.confidence
        + _inv(stress_score) * aw.inv_stress
        + _inv(min(steering_instability * sw.steering_gain, 100.0)) * aw.inv_steering_instability
        + _inv(min(micro_correction * 5.0, 100.0)) * aw.inv_micro_correction
    )

    srw = weights.STRATEGIC
    strategic_reliability = _clamp(
        confidence_score * srw.confidence
        + attention_stability * srw.attention
        + _inv(fatigue_score) * srw.inv_fatigue
        + _inv(min(panic_oscillation * 3.0, 100.0)) * srw.inv_panic
    )

    pw = weights.PANIC
    panic_probability = _clamp(
        min(panic_oscillation * pw.panic_oscillation_gain, 100.0)
        * (1.0 - pw.stress_term - pw.tunnel_vision_term)
        + stress_score * pw.stress_term
        + tunnel_vision_prob * pw.tunnel_vision_term
    )

    persona_state = persona.classify(
        stress=stress_score,
        confidence=confidence_score,
        fatigue=fatigue_score,
        panic_oscillation=panic_oscillation,
        throttle_commitment=throttle_commitment,
    )

    return {
        "stress_score": round(stress_score, 3),
        "confidence_score": round(confidence_score, 3),
        "fatigue_score": round(fatigue_score, 3),
        "cognitive_load_score": round(cognitive_load_score, 3),
        "attention_stability": round(attention_stability, 3),
        "strategic_reliability": round(strategic_reliability, 3),
        "panic_probability": round(panic_probability, 3),
        "tunnel_vision_prob": round(tunnel_vision_prob, 3),
        "persona_state": persona_state,
    }


@dataclass(frozen=True)
class TrajectoryPoint:
    timestamp: str
    baseline: Dict[str, float]
    counterfactual: Dict[str, float]
    delta: Dict[str, float]


def replay_trajectory(
    rows: List[Dict[str, Any]],
    mutations: List[Dict[str, Any]],
) -> List[TrajectoryPoint]:
    """Re-run the cognitive maths under baseline and mutated inputs.

    Mutations apply once per row in the window, so the same mutation can
    be threaded across the whole window (e.g. lower synthetic_hr by 8 for
    every tick) without restating the path.
    """
    baseline_fatigue: List[float] = []
    counter_fatigue: List[float] = []
    trajectory: List[TrajectoryPoint] = []

    for row in rows:
        inputs = row.get("inputs", {})
        baseline_state = _recompute_cognitive(
            inputs.get("features", {}) or {},
            inputs.get("biometrics", {}) or {},
            baseline_fatigue,
        )

        mutated_row = apply_mutations(row, mutations)
        mutated_inputs = mutated_row.get("inputs", {})
        counter_state = _recompute_cognitive(
            mutated_inputs.get("features", {}) or {},
            mutated_inputs.get("biometrics", {}) or {},
            counter_fatigue,
        )

        delta = {
            field_: round(counter_state[field_] - baseline_state[field_], 3)
            for field_ in COGNITIVE_FIELDS
            if isinstance(baseline_state.get(field_), (int, float))
        }

        trajectory.append(
            TrajectoryPoint(
                timestamp=str(row.get("timestamp", "")),
                baseline=baseline_state,
                counterfactual=counter_state,
                delta=delta,
            )
        )

    return trajectory


def summarise_trajectory(trajectory: List[TrajectoryPoint]) -> Dict[str, Any]:
    if not trajectory:
        return {
            "baseline_avg": {field_: 0.0 for field_ in COGNITIVE_FIELDS},
            "counterfactual_avg": {field_: 0.0 for field_ in COGNITIVE_FIELDS},
            "delta_avg": {field_: 0.0 for field_ in COGNITIVE_FIELDS},
            "biggest_delta_field": None,
            "biggest_delta_value": 0.0,
        }

    fields = COGNITIVE_FIELDS
    baseline_sums = {field_: 0.0 for field_ in fields}
    counter_sums = {field_: 0.0 for field_ in fields}
    delta_sums = {field_: 0.0 for field_ in fields}
    n = len(trajectory)
    for point in trajectory:
        for field_ in fields:
            baseline_sums[field_] += float(point.baseline.get(field_, 0.0) or 0.0)
            counter_sums[field_] += float(point.counterfactual.get(field_, 0.0) or 0.0)
            delta_sums[field_] += float(point.delta.get(field_, 0.0) or 0.0)

    baseline_avg = {field_: round(baseline_sums[field_] / n, 3) for field_ in fields}
    counter_avg = {field_: round(counter_sums[field_] / n, 3) for field_ in fields}
    delta_avg = {field_: round(delta_sums[field_] / n, 3) for field_ in fields}

    biggest_field, biggest_value = max(
        delta_avg.items(),
        key=lambda kv: abs(kv[1]),
        default=(None, 0.0),
    )

    return {
        "baseline_avg": baseline_avg,
        "counterfactual_avg": counter_avg,
        "delta_avg": delta_avg,
        "biggest_delta_field": biggest_field,
        "biggest_delta_value": round(biggest_value, 3),
    }


def build_rationale(summary: Dict[str, Any], mutations: List[Dict[str, Any]]) -> str:
    if not mutations:
        return "No mutations applied. Counterfactual matches baseline by construction."
    biggest = summary.get("biggest_delta_field")
    biggest_val = summary.get("biggest_delta_value", 0.0)
    mut_labels = ", ".join(f"{m.get('target')}={m.get('value')}" for m in mutations)
    if biggest is None:
        return f"Applied mutations [{mut_labels}] but the cognitive trajectory did not diverge measurably."
    direction = "lower" if biggest_val < 0 else "higher"
    return (
        f"With mutations [{mut_labels}] applied to the audit window, the cognitive trajectory "
        f"diverged most on {biggest}: {direction} by {abs(biggest_val):.2f} on average across the window."
    )
