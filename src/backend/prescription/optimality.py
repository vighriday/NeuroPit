"""Optimality Gap calculator.

Given a driver's current cognitive twin and the Driver Performance
Envelope projection, this module computes:

- `cognitive_efficiency` on a zero to one hundred scale where one hundred
  means the driver is sitting exactly on their fast lap centroid.
- `performance_lost_s` an estimate of how much laptime the driver is
  leaving on the table this lap because of cognitive distance from the
  envelope.
- A signed per dimension contribution so the strategist can see which
  axis is hurting most (e.g. confidence -22 means confidence is twenty
  two points below the envelope centroid for this driver).

The numbers are interpretable. There is no learned model in this file.
Every constant is documented in docs/COGNITIVE_METHODOLOGY.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional

from src.backend.prescription.envelope import (
    COGNITIVE_DIMENSIONS,
    DIMENSION_WEIGHTS,
    DISTANCE_TO_SECONDS,
    DriverPerformanceEnvelope,
    EnvelopeProjection,
)


# Map the weighted Euclidean distance to a 0-100 efficiency by passing it
# through a smooth decay. distance 0.0 -> efficiency 100, distance 1.0 ->
# efficiency ~61, distance 2.0 -> efficiency ~14. The shape was chosen so
# small drifts inside the tolerance band do not panic the operator but
# bigger drifts collapse the score quickly.
EFFICIENCY_DECAY = 0.5


@dataclass(frozen=True)
class OptimalityReport:
    driver_id: str
    timestamp: str
    cognitive_efficiency: float
    performance_lost_s: float
    weighted_distance: float
    centroid: Dict[str, float]
    tolerances: Dict[str, float]
    deltas: Dict[str, float]
    contributions: Dict[str, float]
    sample_count: int
    persona_seed: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "driver_id": self.driver_id,
            "timestamp": self.timestamp,
            "cognitive_efficiency": self.cognitive_efficiency,
            "performance_lost_s": self.performance_lost_s,
            "weighted_distance": self.weighted_distance,
            "centroid": self.centroid,
            "tolerances": self.tolerances,
            "deltas": self.deltas,
            "contributions": self.contributions,
            "sample_count": self.sample_count,
            "persona_seed": self.persona_seed,
        }


def _distance_to_efficiency(distance: float) -> float:
    if distance <= 0.0:
        return 100.0
    score = 100.0 * math.exp(-EFFICIENCY_DECAY * distance)
    return float(max(0.0, min(100.0, score)))


def _distance_to_lost_seconds(distance: float) -> float:
    """Map the weighted distance to an estimated lap delta in seconds."""
    return float(max(0.0, distance * DISTANCE_TO_SECONDS))


def _per_dimension_contributions(projection: EnvelopeProjection) -> Dict[str, float]:
    """Return the share of weighted distance attributable to each dimension."""
    raw: Dict[str, float] = {}
    total = 0.0
    for dim in COGNITIVE_DIMENSIONS:
        tolerance = max(projection.tolerances[dim], 1e-6)
        contribution = DIMENSION_WEIGHTS[dim] * (projection.deltas[dim] / tolerance) ** 2
        raw[dim] = contribution
        total += contribution
    if total <= 0.0:
        return {dim: 0.0 for dim in COGNITIVE_DIMENSIONS}
    return {dim: round(raw[dim] / total, 4) for dim in COGNITIVE_DIMENSIONS}


def compute_optimality(
    state: Dict[str, object],
    envelope: DriverPerformanceEnvelope,
    *,
    driver_id: Optional[str] = None,
    timestamp: Optional[str] = None,
) -> OptimalityReport:
    """Compute the optimality report for a single cognitive evaluation."""
    resolved_driver = str(driver_id or state.get("driver_id") or "")
    resolved_ts = str(timestamp or state.get("timestamp") or "")
    projection = envelope.project(resolved_driver, state)  # type: ignore[arg-type]

    efficiency = _distance_to_efficiency(projection.weighted_distance)
    lost_seconds = _distance_to_lost_seconds(projection.weighted_distance)
    contributions = _per_dimension_contributions(projection)

    return OptimalityReport(
        driver_id=resolved_driver,
        timestamp=resolved_ts,
        cognitive_efficiency=round(efficiency, 2),
        performance_lost_s=round(lost_seconds, 3),
        weighted_distance=projection.weighted_distance,
        centroid=projection.centroid,
        tolerances=projection.tolerances,
        deltas=projection.deltas,
        contributions=contributions,
        sample_count=projection.sample_count,
        persona_seed=projection.persona_seed,
    )
