"""Cognitive Prescriptive Engine.

The Cognitive Twin is diagnostic. This package converts it into prescriptive
pit wall actions. Every prescription carries a typed action label, a
quantified optimality gap, a projected counterfactual twin, and a Granite
reasoning paragraph. Every prescription is auditable.

Modules:
    envelope.py    Driver Performance Envelope - empirical per driver model
                   of which cognitive states tend to produce fast laps for
                   that driver. Bootstrapped from priors then refined online.
    optimality.py  Optimality Gap calculator. Given the current twin, returns
                   the driver's cognitive efficiency on a zero to one hundred
                   scale plus the estimated seconds of performance left on
                   the table this lap.
    actions.py     Typed action space and guardrail rules. The prescription
                   engine can only emit actions defined here.
    engine.py      Top level prescription engine. Composes the envelope, the
                   optimality gap, the action space, and Granite explainer
                   into a single emit() call.
"""

from src.backend.prescription.engine import PrescriptionEngine, Prescription
from src.backend.prescription.envelope import DriverPerformanceEnvelope
from src.backend.prescription.optimality import OptimalityReport, compute_optimality
from src.backend.prescription.actions import (
    ACTION_SPACE,
    PrescribedAction,
    ActionGuardrail,
)

__all__ = [
    "PrescriptionEngine",
    "Prescription",
    "DriverPerformanceEnvelope",
    "OptimalityReport",
    "compute_optimality",
    "ACTION_SPACE",
    "PrescribedAction",
    "ActionGuardrail",
]
