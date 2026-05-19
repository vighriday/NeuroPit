"""Trust and uncertainty layer.

Every cognitive output ships with a confidence band so the dashboard never
displays a number on its own. The rules of thumb here come straight from
`docs/COGNITIVE_METHODOLOGY.md`. Keep the two in sync.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


EXPECTED_TELEMETRY_FIELDS = (
    "speed",
    "rpm",
    "gear",
    "throttle",
    "brake",
    "steering_angle",
)


@dataclass(frozen=True)
class TrustReport:
    band: str
    data_completeness: float
    sensor_agreement: float

    def to_dict(self) -> dict:
        return {
            "band": self.band,
            "data_completeness": round(self.data_completeness, 3),
            "sensor_agreement": round(self.sensor_agreement, 3),
        }


def data_completeness(frame: dict, expected: Iterable[str] = EXPECTED_TELEMETRY_FIELDS) -> float:
    """Fraction of expected telemetry fields that are present and non null."""
    expected = list(expected)
    if not expected:
        return 1.0
    present = sum(1 for key in expected if frame.get(key) is not None)
    return present / len(expected)


def sensor_agreement(directions: Iterable[float]) -> float:
    """Fraction of contributing signals that move in the same direction.

    The directions argument expects positive numbers when the signal points
    toward higher cognitive load and negative numbers when it points toward
    lower cognitive load. A value of zero counts as neutral and is ignored.
    """
    values = [v for v in directions if v != 0]
    if not values:
        return 1.0
    positives = sum(1 for v in values if v > 0)
    negatives = sum(1 for v in values if v < 0)
    majority = max(positives, negatives)
    return majority / len(values)


def evaluate(frame: dict, signal_directions: Iterable[float]) -> TrustReport:
    completeness = data_completeness(frame)
    agreement = sensor_agreement(signal_directions)

    if completeness >= 0.9 and agreement >= 0.7:
        band = "high"
    elif completeness >= 0.7:
        band = "moderate"
    else:
        band = "unstable"

    return TrustReport(band=band, data_completeness=completeness, sensor_agreement=agreement)
