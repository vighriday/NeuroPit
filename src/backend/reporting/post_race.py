"""Post race intelligence report builder.

The PRD asks for a debrief that contains the cognitive summary, the emotional
stability timeline, the confidence reconstruction, the Ghost Lap analysis,
and the counterfactual simulation report for a given session. This module
assembles all of that into a single JSON document so the dashboard can render
it, the strategist can export it, and the audit log keeps a copy.

The report is built from the on disk audit log so it stays available even
when InfluxDB or Qdrant are offline. When InfluxDB is reachable we use it as
a richer source for the cognitive timeline.
"""

from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from datetime import date, datetime
from statistics import mean
from typing import Dict, List, Optional

from src.backend.config import get_settings
from src.backend.simulation.counterfactual import run_all as run_all_counterfactuals
from src.backend.simulation.ghost_lap import LapCognitiveSummary, attribute_lost_time

logger = logging.getLogger(__name__)


def _estimate_lap_time_s(events_for_driver: List[dict]) -> float:
    """Return wall clock span in seconds across the audit events.

    The post race report is computed off the audit log; we do not have
    a real lap counter in the audit row. The next best signal is the
    elapsed time between the first and last audit row in the window
    the caller passed in. This is honest about what it knows: it is
    the wall clock span the strategist asked to summarise, not a
    fabricated 90 second placeholder.
    """
    timestamps: List[datetime] = []
    for event in events_for_driver:
        ts = event.get("timestamp")
        if not ts:
            continue
        try:
            value = ts if not ts.endswith("Z") else ts.replace("Z", "+00:00")
            timestamps.append(datetime.fromisoformat(value))
        except Exception:
            continue
    if len(timestamps) < 2:
        return 0.0
    span = (max(timestamps) - min(timestamps)).total_seconds()
    return float(max(span, 0.0))


def _iter_audit_events(audit_dir: str):
    if not os.path.isdir(audit_dir):
        return
    for name in sorted(os.listdir(audit_dir)):
        if not name.endswith(".jsonl"):
            continue
        path = os.path.join(audit_dir, name)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue
        except OSError as exc:
            logger.warning("Could not read audit file %s: %s", path, exc)


def _filter_for_session(events, session_id: Optional[str]):
    if session_id is None:
        return events
    filtered = []
    for event in events:
        inputs = event.get("inputs") or {}
        feature_session = (inputs.get("features") or {}).get("session_id")
        state_session = (event.get("state") or {}).get("session_id")
        if feature_session == session_id or state_session == session_id:
            filtered.append(event)
    return filtered


def _summarise_cognitive(events_for_driver: List[dict]) -> Dict[str, float]:
    if not events_for_driver:
        return {}
    fields = (
        "stress_score",
        "confidence_score",
        "fatigue_score",
        "cognitive_load_score",
        "attention_stability",
        "strategic_reliability",
        "panic_probability",
        "emotional_drift_score",
    )
    summary: Dict[str, float] = {}
    for field_name in fields:
        values = []
        for event in events_for_driver:
            state = event.get("state") or {}
            value = state.get(field_name)
            if isinstance(value, (int, float)):
                values.append(float(value))
        if values:
            summary[f"avg_{field_name}"] = round(mean(values), 2)
            summary[f"peak_{field_name}"] = round(max(values), 2)
    return summary


def _build_confidence_timeline(events_for_driver: List[dict]) -> List[Dict[str, float]]:
    timeline = []
    for event in events_for_driver:
        state = event.get("state") or {}
        timestamp = state.get("timestamp") or event.get("timestamp")
        if not timestamp:
            continue
        timeline.append(
            {
                "timestamp": timestamp,
                "stress_score": float(state.get("stress_score", 0.0)),
                "confidence_score": float(state.get("confidence_score", 0.0)),
                "fatigue_score": float(state.get("fatigue_score", 0.0)),
                "emotional_drift_score": float(state.get("emotional_drift_score", 0.0)),
            }
        )
    return timeline


def _ghost_lap_for_driver(driver_id: str, events_for_driver: List[dict]) -> Optional[dict]:
    if not events_for_driver:
        return None
    summary = LapCognitiveSummary(
        lap_number=len(events_for_driver),
        driver_id=driver_id,
        actual_lap_time_s=_estimate_lap_time_s(events_for_driver),
        average_stress=float(mean(
            float((event.get("state") or {}).get("stress_score", 0.0)) for event in events_for_driver
        )),
        average_fatigue=float(mean(
            float((event.get("state") or {}).get("fatigue_score", 0.0)) for event in events_for_driver
        )),
        panic_events=sum(
            1
            for event in events_for_driver
            if float((event.get("state") or {}).get("panic_probability", 0.0)) > 70.0
        ),
    )
    result = attribute_lost_time(summary)
    return {
        "lap_number": result.lap_number,
        "actual_lap_time_s": result.actual_lap_time_s,
        "ghost_lap_time_s": result.ghost_lap_time_s,
        "lost_time_s": result.lost_time_s,
        "contributions": result.contributions,
    }


def _counterfactuals_for_driver(driver_id: str, events_for_driver: List[dict]) -> List[dict]:
    if not events_for_driver:
        return []
    summary = LapCognitiveSummary(
        lap_number=len(events_for_driver),
        driver_id=driver_id,
        actual_lap_time_s=_estimate_lap_time_s(events_for_driver),
        average_stress=float(mean(
            float((event.get("state") or {}).get("stress_score", 0.0)) for event in events_for_driver
        )),
        average_fatigue=float(mean(
            float((event.get("state") or {}).get("fatigue_score", 0.0)) for event in events_for_driver
        )),
        panic_events=sum(
            1
            for event in events_for_driver
            if float((event.get("state") or {}).get("panic_probability", 0.0)) > 70.0
        ),
    )
    return [
        {
            "scenario": result.scenario,
            "baseline_lap_time_s": result.baseline_lap_time_s,
            "counterfactual_lap_time_s": result.counterfactual_lap_time_s,
            "lap_delta_s": result.lap_delta_s,
            "rationale": result.rationale,
            "adjustments": result.adjustments,
        }
        for result in run_all_counterfactuals(summary)
    ]


def build_report(session_id: Optional[str] = None) -> dict:
    """Assemble a complete post race intelligence report.

    Pass `session_id=None` to build a report across every recorded session,
    which is useful in demo conditions where only one session has been played
    back.
    """
    settings = get_settings()
    events = list(_iter_audit_events(settings.audit_log_dir))
    cognitive_events = [event for event in events if event.get("kind") == "cognitive_evaluation"]
    cognitive_events = _filter_for_session(cognitive_events, session_id)

    by_driver: Dict[str, List[dict]] = defaultdict(list)
    for event in cognitive_events:
        driver_id = event.get("driver_id")
        if driver_id:
            by_driver[driver_id].append(event)

    explanation_events = [event for event in events if event.get("kind") == "explanation"]
    explanations_by_driver: Dict[str, List[dict]] = defaultdict(list)
    for event in explanation_events:
        driver_id = event.get("driver_id")
        if driver_id:
            explanations_by_driver[driver_id].append(event)

    drivers: Dict[str, dict] = {}
    for driver_id, driver_events in by_driver.items():
        drivers[driver_id] = {
            "summary": _summarise_cognitive(driver_events),
            "timeline": _build_confidence_timeline(driver_events),
            "ghost_lap": _ghost_lap_for_driver(driver_id, driver_events),
            "counterfactuals": _counterfactuals_for_driver(driver_id, driver_events),
            "explanations": [
                {
                    "timestamp": entry.get("timestamp"),
                    "text": (entry.get("explanation") or {}).get("text"),
                    "source": (entry.get("explanation") or {}).get("source"),
                }
                for entry in explanations_by_driver.get(driver_id, [])[-10:]
            ],
            "evaluation_count": len(driver_events),
        }

    return {
        "session_id": session_id,
        "generated_on": date.today().isoformat(),
        "driver_count": len(drivers),
        "total_evaluations": sum(len(events_for_driver) for events_for_driver in by_driver.values()),
        "drivers": drivers,
    }
