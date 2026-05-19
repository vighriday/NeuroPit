"""Top level Cognitive Prescriptive Engine.

Given a cognitive evaluation and an optional five second failure forecast,
emit a ranked list of pit wall actions plus a primary recommendation,
projected counterfactual twin, and an optimality report. Every emission
carries the rule names that contributed to the score so the call is
auditable.

The scoring approach is explicit. Each action has a base score, a set of
bonuses that activate when the relevant cognitive signal is present, and
a hard guardrail set that can veto the action regardless of score. The
engine never invents new actions. It composes the documented action space
with the documented optimality report.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from src.backend.prescription.actions import (
    ACTION_SPACE,
    GUARDRAILS,
    PrescribedAction,
    get_action,
    guardrails_blocked,
)
from src.backend.prescription.envelope import (
    COGNITIVE_DIMENSIONS,
    DriverPerformanceEnvelope,
)
from src.backend.prescription.optimality import OptimalityReport, compute_optimality


@dataclass(frozen=True)
class RankedAction:
    code: str
    label: str
    surface: str
    summary: str
    score: float
    triggers: Tuple[str, ...]
    blocked_by: Tuple[str, ...]
    projected_twin: Dict[str, float]
    projected_efficiency: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "code": self.code,
            "label": self.label,
            "surface": self.surface,
            "summary": self.summary,
            "score": round(self.score, 4),
            "triggers": list(self.triggers),
            "blocked_by": list(self.blocked_by),
            "projected_twin": self.projected_twin,
            "projected_efficiency": round(self.projected_efficiency, 2),
        }


@dataclass(frozen=True)
class Prescription:
    driver_id: str
    timestamp: str
    optimality: OptimalityReport
    primary: RankedAction
    alternatives: Tuple[RankedAction, ...]
    rationale: str
    forecast_used: bool

    def to_dict(self) -> Dict[str, object]:
        return {
            "driver_id": self.driver_id,
            "timestamp": self.timestamp,
            "optimality": self.optimality.to_dict(),
            "primary": self.primary.to_dict(),
            "alternatives": [a.to_dict() for a in self.alternatives],
            "rationale": self.rationale,
            "forecast_used": self.forecast_used,
        }


def _clip_0_100(value: float) -> float:
    return float(max(0.0, min(100.0, value)))


def _project_twin(state: Dict[str, float], action: PrescribedAction) -> Dict[str, float]:
    projected = dict(state)
    for dim, delta in action.effect.items():
        base = float(projected.get(dim, 0.0))
        projected[dim] = _clip_0_100(base + delta)
    return projected


def _efficiency_of(state: Dict[str, float], envelope: DriverPerformanceEnvelope, driver_id: str) -> float:
    projection = envelope.project(driver_id, state)
    from src.backend.prescription.optimality import _distance_to_efficiency

    return _distance_to_efficiency(projection.weighted_distance)


def _forecast_panic_probability(forecast: Optional[Dict[str, object]]) -> float:
    if not forecast:
        return 0.0
    horizons = forecast.get("horizons") or {}
    if not isinstance(horizons, dict):
        return 0.0
    for key in ("5s", "5", "five_seconds"):
        if key in horizons:
            block = horizons[key]
            if isinstance(block, dict) and "panic_collapse" in block:
                try:
                    return float(block["panic_collapse"]) * 100.0
                except (TypeError, ValueError):
                    return 0.0
    return 0.0


def _action_score(
    action: PrescribedAction,
    state: Dict[str, float],
    optimality: OptimalityReport,
    forecast_panic: float,
) -> Tuple[float, List[str]]:
    """Score one action against the current state, return (score, triggers)."""
    stress = float(state.get("stress_score", 0.0))
    confidence = float(state.get("confidence_score", 0.0))
    fatigue = float(state.get("fatigue_score", 0.0))
    panic = float(state.get("panic_probability", 0.0))
    cognitive_load = float(state.get("cognitive_load_score", 0.0))
    emotional_drift = float(state.get("emotional_drift_score", 0.0))
    attention = float(state.get("attention_stability", 0.0))
    persona = str(state.get("persona_state", "Recovery"))

    triggers: List[str] = []
    score = 0.0
    inefficiency = max(0.0, 100.0 - optimality.cognitive_efficiency)

    if action.code == "hold_position":
        # Baseline action. Wins when the twin sits inside the envelope and
        # neither the forecast nor the persona drift threatens.
        score = max(0.0, optimality.cognitive_efficiency - 40.0) * 0.6
        if forecast_panic < 25.0 and persona in ("Flow State", "Recovery"):
            score += 25.0
            triggers.append("inside_envelope_no_threat")
        if optimality.cognitive_efficiency > 75.0:
            triggers.append("efficiency_above_75")
            score += 10.0

    elif action.code == "radio_calm":
        if stress > 60.0:
            score += stress - 60.0
            triggers.append("stress_above_60")
        if panic > 35.0:
            score += panic * 0.5
            triggers.append("panic_above_35")
        if forecast_panic > 35.0:
            score += forecast_panic * 0.4
            triggers.append("forecast_panic_above_35")
        if cognitive_load > 65.0:
            score += (cognitive_load - 65.0) * 0.4
            triggers.append("cognitive_load_above_65")

    elif action.code == "radio_push":
        if confidence > 70.0:
            score += (confidence - 70.0) * 0.8
            triggers.append("confidence_above_70")
        if persona == "Flow State":
            score += 25.0
            triggers.append("persona_flow_state")
        if optimality.cognitive_efficiency > 70.0:
            score += (optimality.cognitive_efficiency - 70.0) * 0.6
            triggers.append("efficiency_above_70")
        if stress > 60.0:
            score *= 0.4
        if forecast_panic > 40.0:
            # Even a Flow State driver should not be pushed when the
            # five second forecast carries a panic collapse risk.
            score *= max(0.0, 1.0 - forecast_panic / 100.0)

    elif action.code == "radio_reduce_information":
        if cognitive_load > 70.0:
            score += (cognitive_load - 70.0) * 0.9
            triggers.append("cognitive_load_above_70")
        if attention < 50.0:
            score += (50.0 - attention) * 0.6
            triggers.append("attention_below_50")

    elif action.code == "lift_aggression":
        if persona == "Aggressive" and inefficiency > 20.0:
            score += inefficiency * 0.7
            triggers.append("aggressive_outside_envelope")
        if stress > 70.0 and confidence < 70.0:
            score += (stress - 70.0) * 0.5
            triggers.append("stress_outpacing_confidence")

    elif action.code == "request_undercut_window":
        if confidence > 65.0 and optimality.cognitive_efficiency > 65.0:
            score += min(confidence, optimality.cognitive_efficiency) - 60.0
            triggers.append("confidence_and_efficiency_above_65")
        if persona == "Flow State":
            score += 8.0
            triggers.append("persona_flow_state")

    elif action.code == "defensive_mode":
        if confidence < 50.0:
            score += (50.0 - confidence) * 0.9
            triggers.append("confidence_below_50")
        if emotional_drift > 50.0:
            score += (emotional_drift - 50.0) * 0.6
            triggers.append("emotional_drift_above_50")
        if persona == "Defensive":
            score += 10.0
            triggers.append("persona_defensive")

    elif action.code == "recovery_lap":
        if fatigue > 65.0:
            score += (fatigue - 65.0) * 0.9
            triggers.append("fatigue_above_65")
        if persona == "Fatigue":
            score += 15.0
            triggers.append("persona_fatigue")
        if emotional_drift > 60.0:
            score += (emotional_drift - 60.0) * 0.5
            triggers.append("emotional_drift_above_60")

    elif action.code == "box_now":
        if panic > 60.0:
            score += panic
            triggers.append("panic_above_60")
        if forecast_panic > 55.0:
            score += forecast_panic
            triggers.append("forecast_panic_above_55")
        if float(state.get("tunnel_vision_prob", 0.0)) > 50.0:
            score += 30.0
            triggers.append("tunnel_vision_above_50")
        if persona == "Panic":
            score += 25.0
            triggers.append("persona_panic")

    return float(max(0.0, score)), triggers


@dataclass
class PrescriptionEngine:
    """Stateful top level engine.

    Composes the Driver Performance Envelope, the optimality report, and
    the typed action space into a ranked prescription.
    """

    envelope: DriverPerformanceEnvelope = field(default_factory=DriverPerformanceEnvelope)

    def emit(
        self,
        state: Dict[str, object],
        forecast: Optional[Dict[str, object]] = None,
    ) -> Prescription:
        driver_id = str(state.get("driver_id", ""))
        timestamp = str(state.get("timestamp", ""))
        confidence_band = str(state.get("confidence_band", "moderate"))

        is_fast_signal = confidence_band == "high"
        # Always refine the envelope so the model converges, but only with
        # confident readings.
        self.envelope.observe(driver_id, state, is_fast_lap_signal=is_fast_signal)

        optimality = compute_optimality(
            state=state,
            envelope=self.envelope,
            driver_id=driver_id,
            timestamp=timestamp,
        )

        forecast_panic = _forecast_panic_probability(forecast)

        ranked: List[RankedAction] = []
        for action in ACTION_SPACE:
            score, triggers = _action_score(action, state, optimality, forecast_panic)  # type: ignore[arg-type]
            blocked = guardrails_blocked(action.code, state)  # type: ignore[arg-type]
            projected = _project_twin(state, action)  # type: ignore[arg-type]
            projected_eff = _efficiency_of(projected, self.envelope, driver_id)
            ranked.append(
                RankedAction(
                    code=action.code,
                    label=action.label,
                    surface=action.surface,
                    summary=action.summary,
                    score=score,
                    triggers=tuple(triggers),
                    blocked_by=tuple(blocked),
                    projected_twin={
                        k: round(float(projected.get(k, 0.0)), 2)
                        for k in COGNITIVE_DIMENSIONS
                    },
                    projected_efficiency=projected_eff,
                )
            )

        ranked.sort(key=lambda r: (-1 if not r.blocked_by else 0, r.score), reverse=True)
        # Sorting trick above forces blocked actions to the bottom of the
        # ranking regardless of their raw score. The primary recommendation
        # is the highest scoring non blocked action.
        primary = next((r for r in ranked if not r.blocked_by), ranked[0])
        alternatives = tuple(r for r in ranked if r.code != primary.code)[:3]

        rationale = self._build_rationale(state, optimality, primary, forecast_panic)

        return Prescription(
            driver_id=driver_id,
            timestamp=timestamp,
            optimality=optimality,
            primary=primary,
            alternatives=alternatives,
            rationale=rationale,
            forecast_used=bool(forecast),
        )

    @staticmethod
    def _build_rationale(
        state: Dict[str, object],
        optimality: OptimalityReport,
        primary: RankedAction,
        forecast_panic: float,
    ) -> str:
        persona = str(state.get("persona_state", "Recovery"))
        band = str(state.get("confidence_band", "moderate"))
        eff = optimality.cognitive_efficiency
        lost = optimality.performance_lost_s
        top_dim = max(
            optimality.contributions.items(),
            key=lambda kv: kv[1],
            default=("none", 0.0),
        )
        dim_label = top_dim[0].replace("_score", "").replace("_", " ")
        chunks = [
            f"Persona {persona} on a {band} confidence band.",
            f"Cognitive efficiency {eff:.0f}/100 with {lost:.2f}s left on the table.",
            f"Biggest envelope drift on {dim_label}.",
            f"Prescribed action: {primary.label}.",
        ]
        if forecast_panic > 35.0:
            chunks.append(
                f"Five second forecast carries a {forecast_panic:.0f}% panic collapse probability."
            )
        if primary.blocked_by:
            chunks.append(
                "All higher scoring actions were vetoed by safety guardrails."
            )
        return " ".join(chunks)
