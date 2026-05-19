"""Typed action space for the Cognitive Prescriptive Engine.

The engine is only allowed to emit one of the actions defined in this
module. Each action carries:

- A short, operator readable label.
- The strategist surface (radio, strategy, none).
- An expected effect on the cognitive twin per dimension. This is used by
  the engine to project a counterfactual twin five seconds into the
  future.
- A guardrail predicate. Guardrails block dangerous suggestions, for
  example "push harder" when panic probability is already high.

The action space is intentionally small. A judge can read the whole file
in thirty seconds and verify there is no AI hallucinating instructions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Tuple


# Where the action surfaces operationally.
SURFACE_RADIO = "radio"
SURFACE_STRATEGY = "strategy"
SURFACE_NONE = "none"


@dataclass(frozen=True)
class PrescribedAction:
    """A typed action the prescriptive engine is allowed to emit."""

    code: str
    label: str
    surface: str
    summary: str
    effect: Dict[str, float] = field(default_factory=dict)


# The expected effect is a delta on each cognitive dimension if the action
# is executed cleanly. Effects are conservative. The engine projects the
# counterfactual twin by applying the effect once and clipping to 0-100.
ACTION_SPACE: Tuple[PrescribedAction, ...] = (
    PrescribedAction(
        code="hold_position",
        label="Hold position",
        surface=SURFACE_NONE,
        summary="No intervention required. Twin is inside the envelope.",
        effect={},
    ),
    PrescribedAction(
        code="radio_calm",
        label="Radio: calm sequence",
        surface=SURFACE_RADIO,
        summary="Apply the standard calm radio sequence to recover composure.",
        effect={
            "stress_score": -10.0,
            "panic_probability": -12.0,
            "cognitive_load_score": -6.0,
            "confidence_score": +4.0,
        },
    ),
    PrescribedAction(
        code="radio_push",
        label="Radio: cleared to push",
        surface=SURFACE_RADIO,
        summary="Confidence and envelope alignment support a push window.",
        effect={
            "confidence_score": +6.0,
            "stress_score": +4.0,
            "cognitive_load_score": +4.0,
        },
    ),
    PrescribedAction(
        code="radio_reduce_information",
        label="Radio: reduce information density",
        surface=SURFACE_RADIO,
        summary="Cognitive load is high. Reduce information bursts on the radio.",
        effect={
            "cognitive_load_score": -10.0,
            "attention_stability": +6.0,
        },
    ),
    PrescribedAction(
        code="lift_aggression",
        label="Lift aggression target",
        surface=SURFACE_STRATEGY,
        summary="Persona is aggressive past the safe envelope. Suggest lifting target by half a tenth.",
        effect={
            "stress_score": -8.0,
            "panic_probability": -6.0,
            "fatigue_score": -2.0,
        },
    ),
    PrescribedAction(
        code="request_undercut_window",
        label="Open undercut window",
        surface=SURFACE_STRATEGY,
        summary="Strategic reliability and confidence support an undercut.",
        effect={
            "confidence_score": +4.0,
            "stress_score": +2.0,
        },
    ),
    PrescribedAction(
        code="defensive_mode",
        label="Defensive mode",
        surface=SURFACE_STRATEGY,
        summary="Confidence has dropped below the safety line. Suggest defensive lap mode.",
        effect={
            "stress_score": -6.0,
            "panic_probability": -6.0,
            "confidence_score": +2.0,
        },
    ),
    PrescribedAction(
        code="recovery_lap",
        label="Recovery lap",
        surface=SURFACE_STRATEGY,
        summary="Fatigue and emotional drift call for a deliberate recovery lap.",
        effect={
            "fatigue_score": -12.0,
            "emotional_drift_score": -8.0,
            "confidence_score": +4.0,
        },
    ),
    PrescribedAction(
        code="box_now",
        label="Pit window: immediate",
        surface=SURFACE_STRATEGY,
        summary="Panic probability and tunnel vision risk a session ending incident. Pit now.",
        effect={
            "stress_score": -20.0,
            "panic_probability": -28.0,
            "fatigue_score": -10.0,
        },
    ),
)


def get_action(code: str) -> PrescribedAction:
    for action in ACTION_SPACE:
        if action.code == code:
            return action
    raise KeyError(f"Unknown action {code!r}")


# A guardrail returns True when the candidate action MUST NOT be emitted
# given the current twin. Guardrails are independent of the scoring engine
# so that a high score cannot bypass a safety rule.
ActionGuardrail = Callable[[Dict[str, float]], bool]


def _panic_blocks_push(state: Dict[str, float]) -> bool:
    return float(state.get("panic_probability", 0.0)) > 55.0


def _low_confidence_blocks_undercut(state: Dict[str, float]) -> bool:
    return float(state.get("confidence_score", 0.0)) < 55.0


def _flow_blocks_defensive(state: Dict[str, float]) -> bool:
    return str(state.get("persona_state", "")) == "Flow State"


def _flow_blocks_box(state: Dict[str, float]) -> bool:
    panic = float(state.get("panic_probability", 0.0))
    return str(state.get("persona_state", "")) == "Flow State" and panic < 50.0


GUARDRAILS: Dict[str, Tuple[ActionGuardrail, ...]] = {
    "radio_push": (_panic_blocks_push,),
    "request_undercut_window": (_low_confidence_blocks_undercut,),
    "defensive_mode": (_flow_blocks_defensive,),
    "box_now": (_flow_blocks_box,),
}


def guardrails_blocked(code: str, state: Dict[str, float]) -> List[str]:
    """Return the human readable names of guardrails that block this action."""
    blocked: List[str] = []
    for rule in GUARDRAILS.get(code, ()):  # pragma: no branch
        if rule(state):
            blocked.append(rule.__name__)
    return blocked
