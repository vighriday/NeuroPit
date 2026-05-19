"""Multi agent strategy parliament.

The PRD describes seven specialised agents that debate race strategy and
hand IBM Granite a consensus to synthesise. We keep each agent intentionally
simple in V1. Every agent reads the same race state input and emits a
proposal with a confidence score and a one line rationale. The parliament
then aggregates the proposals into a single recommendation. Granite reads
the parliament transcript and writes the final natural language summary.

The maths is small enough to read on one page. That is the point. A real
team principal will not act on a recommendation they cannot defend, and
this transcript is the defence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


PIT_NOW = "pit_now"
STAY_OUT = "stay_out"
ATTACK = "attack"
HOLD_POSITION = "hold_position"
DEFEND = "defend"

ALLOWED_PROPOSALS = (PIT_NOW, STAY_OUT, ATTACK, HOLD_POSITION, DEFEND)


@dataclass(frozen=True)
class AgentProposal:
    agent: str
    proposal: str
    confidence: float
    rationale: str


@dataclass
class ParliamentReport:
    proposals: List[AgentProposal]
    consensus: str
    consensus_confidence: float
    transcript: str = ""
    margin_over_runner_up: float = 0.0
    tally: Dict[str, float] = field(default_factory=dict)


def _aggressive_agent(state: dict) -> AgentProposal:
    confidence = float(state.get("confidence_score", 0.0)) / 100.0
    stress = float(state.get("stress_score", 0.0)) / 100.0
    persona = state.get("persona_state", "Recovery")
    decision = ATTACK if confidence > 0.6 and stress < 0.7 else HOLD_POSITION
    weight = (confidence * 0.7) + ((1.0 - stress) * 0.3)
    rationale = (
        f"confidence is {confidence:.2f}, stress is {stress:.2f}, persona is {persona}; "
        f"aggressive agent backs {decision}."
    )
    return AgentProposal("aggressive", decision, round(weight, 3), rationale)


def _defensive_agent(state: dict) -> AgentProposal:
    confidence = float(state.get("confidence_score", 0.0)) / 100.0
    fatigue = float(state.get("fatigue_score", 0.0)) / 100.0
    decision = DEFEND if confidence < 0.5 or fatigue > 0.6 else HOLD_POSITION
    weight = ((1.0 - confidence) * 0.6) + (fatigue * 0.4)
    rationale = (
        f"confidence is {confidence:.2f}, fatigue is {fatigue:.2f}; defensive agent backs {decision}."
    )
    return AgentProposal("defensive", decision, round(weight, 3), rationale)


def _tire_preservation_agent(state: dict) -> AgentProposal:
    tire_wear = float(state.get("tire_wear", 0.5))
    decision = PIT_NOW if tire_wear > 0.75 else STAY_OUT
    weight = abs(tire_wear - 0.5) * 2.0
    rationale = f"tire wear is {tire_wear:.2f}; tire preservation agent backs {decision}."
    return AgentProposal("tire_preservation", decision, round(weight, 3), rationale)


def _weather_risk_agent(state: dict) -> AgentProposal:
    rain_probability = float(state.get("rain_probability", 0.0))
    decision = PIT_NOW if rain_probability > 0.6 else STAY_OUT
    weight = rain_probability if rain_probability > 0.6 else (1.0 - rain_probability) * 0.4
    rationale = f"rain probability is {rain_probability:.2f}; weather risk agent backs {decision}."
    return AgentProposal("weather_risk", decision, round(weight, 3), rationale)


def _cognitive_stability_agent(state: dict) -> AgentProposal:
    persona = state.get("persona_state", "Recovery")
    stress = float(state.get("stress_score", 0.0)) / 100.0
    decision = HOLD_POSITION if persona in {"Panic", "Fatigue"} else ATTACK
    weight = 1.0 - stress if decision == ATTACK else stress
    rationale = (
        f"persona is {persona}, stress is {stress:.2f}; cognitive stability agent backs {decision}."
    )
    return AgentProposal("cognitive_stability", decision, round(weight, 3), rationale)


def _overtake_optimization_agent(state: dict) -> AgentProposal:
    confidence = float(state.get("confidence_score", 0.0)) / 100.0
    gap_to_car_ahead = float(state.get("gap_to_car_ahead_s", 99.0))
    decision = ATTACK if confidence > 0.65 and gap_to_car_ahead < 1.5 else HOLD_POSITION
    weight = confidence if decision == ATTACK else (1.0 - confidence)
    rationale = (
        f"confidence is {confidence:.2f}, gap ahead is {gap_to_car_ahead:.2f}s; "
        f"overtake optimisation agent backs {decision}."
    )
    return AgentProposal("overtake_optimization", decision, round(weight, 3), rationale)


def _fatigue_management_agent(state: dict) -> AgentProposal:
    fatigue = float(state.get("fatigue_score", 0.0)) / 100.0
    decision = PIT_NOW if fatigue > 0.7 else HOLD_POSITION
    weight = fatigue if decision == PIT_NOW else (1.0 - fatigue) * 0.5
    rationale = f"fatigue is {fatigue:.2f}; fatigue management agent backs {decision}."
    return AgentProposal("fatigue_management", decision, round(weight, 3), rationale)


_AGENTS = (
    _aggressive_agent,
    _defensive_agent,
    _tire_preservation_agent,
    _weather_risk_agent,
    _cognitive_stability_agent,
    _overtake_optimization_agent,
    _fatigue_management_agent,
)


def _tally_proposals(proposals: List[AgentProposal]) -> Tuple[Dict[str, float], str, float, float]:
    tally: Dict[str, float] = {}
    for prop in proposals:
        if prop.proposal not in ALLOWED_PROPOSALS:
            continue
        tally[prop.proposal] = tally.get(prop.proposal, 0.0) + prop.confidence

    if not tally:
        return tally, HOLD_POSITION, 0.0, 0.0

    ordered = sorted(tally.items(), key=lambda kv: kv[1], reverse=True)
    consensus, top_weight = ordered[0]
    runner_up_weight = ordered[1][1] if len(ordered) > 1 else 0.0
    total = sum(tally.values()) or 1.0
    confidence = top_weight / total
    margin = top_weight - runner_up_weight
    return tally, consensus, round(confidence, 3), round(margin, 3)


def convene(state: dict) -> ParliamentReport:
    proposals = [agent(state) for agent in _AGENTS]
    tally, consensus, confidence, margin = _tally_proposals(proposals)

    transcript_lines = [f"- {p.agent}: {p.proposal} ({p.confidence:.2f}) {p.rationale}" for p in proposals]
    transcript_lines.append(f"consensus: {consensus} with confidence {confidence:.2f} and margin {margin:.2f}")
    transcript = "\n".join(transcript_lines)

    return ParliamentReport(
        proposals=proposals,
        consensus=consensus,
        consensus_confidence=confidence,
        transcript=transcript,
        margin_over_runner_up=margin,
        tally=tally,
    )
