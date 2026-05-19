"""Driver Performance Envelope.

The envelope is an interpretable, non parametric model of which cognitive
twin states tend to produce the driver's fastest laps. For V1 we bootstrap
it from publicly defensible priors per persona, then refine it online from
the cognitive event stream so a long enough session converges onto the
driver's actual signature.

A real F1 team running NeuroPit in production would seed the envelope from
years of telemetry. For the demo we honest about the bootstrap. Every
envelope ships with a `sample_count` field. Mission Control surfaces it so
the operator can see how confident the envelope is.

The shape of the model is deliberately simple. Each driver has a centroid
in five dimensional cognitive space `(stress, confidence, fatigue,
cognitive_load, panic_probability)` and a tolerance vector. The fast lap
projection at any current twin is the centroid. The performance penalty is
the weighted Euclidean distance from the centroid. The lap delta in
seconds is a linear scaling of that distance, anchored so the unit
distance maps to a defensible amount of time.

The envelope is intentionally NOT a deep model. A deep model trained inside
a hackathon window is impossible to defend in a code review. A weighted
centroid is honest. Phase 3 of the roadmap swaps this for a learned model
without changing the contract here.
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional, Tuple


COGNITIVE_DIMENSIONS = (
    "stress_score",
    "confidence_score",
    "fatigue_score",
    "cognitive_load_score",
    "panic_probability",
)


# Per persona priors. The numbers are interpretable and described in
# docs/COGNITIVE_METHODOLOGY.md. A Flow State driver has low stress, high
# confidence, low fatigue, modest cognitive load and near zero panic. An
# Aggressive driver pushes the stress and load axes deliberately. The
# envelope tolerance is wider for noisier states so a single tick does not
# trip the optimality gap unnecessarily.
PERSONA_PRIORS: Dict[str, Dict[str, Tuple[float, float]]] = {
    "Flow State": {
        "stress_score": (28.0, 14.0),
        "confidence_score": (84.0, 8.0),
        "fatigue_score": (24.0, 12.0),
        "cognitive_load_score": (38.0, 12.0),
        "panic_probability": (4.0, 6.0),
    },
    "Aggressive": {
        "stress_score": (62.0, 14.0),
        "confidence_score": (78.0, 10.0),
        "fatigue_score": (44.0, 14.0),
        "cognitive_load_score": (66.0, 14.0),
        "panic_probability": (18.0, 12.0),
    },
    "Defensive": {
        "stress_score": (48.0, 16.0),
        "confidence_score": (54.0, 12.0),
        "fatigue_score": (50.0, 14.0),
        "cognitive_load_score": (52.0, 14.0),
        "panic_probability": (12.0, 10.0),
    },
    "Recovery": {
        "stress_score": (40.0, 16.0),
        "confidence_score": (62.0, 12.0),
        "fatigue_score": (40.0, 14.0),
        "cognitive_load_score": (44.0, 14.0),
        "panic_probability": (10.0, 10.0),
    },
    "Fatigue": {
        "stress_score": (52.0, 16.0),
        "confidence_score": (44.0, 14.0),
        "fatigue_score": (76.0, 10.0),
        "cognitive_load_score": (58.0, 14.0),
        "panic_probability": (14.0, 12.0),
    },
    "Panic": {
        "stress_score": (78.0, 12.0),
        "confidence_score": (38.0, 14.0),
        "fatigue_score": (60.0, 14.0),
        "cognitive_load_score": (78.0, 12.0),
        "panic_probability": (62.0, 14.0),
    },
}


# Per dimension weighting in the distance calculation. Confidence and panic
# matter more for laptime than absolute stress, so we give them a heavier
# coefficient. Documented in docs/COGNITIVE_METHODOLOGY.md alongside the
# rest of the cognitive weights.
DIMENSION_WEIGHTS: Dict[str, float] = {
    "stress_score": 0.18,
    "confidence_score": 0.32,
    "fatigue_score": 0.18,
    "cognitive_load_score": 0.14,
    "panic_probability": 0.18,
}


# Distance to seconds-on-lap anchor. Calibrated so a normalised distance of
# 1.0 (one tolerance band per dimension) maps to ~0.45s of laptime cost.
DISTANCE_TO_SECONDS = 0.45


@dataclass
class EnvelopeCentroid:
    """A single driver's fast lap signature in cognitive space."""

    means: Dict[str, float]
    tolerances: Dict[str, float]
    sample_count: int = 0
    persona_seed: str = "Recovery"


@dataclass
class EnvelopeProjection:
    """The envelope's view of where the driver is vs where they should be."""

    centroid: Dict[str, float]
    tolerances: Dict[str, float]
    deltas: Dict[str, float]
    weighted_distance: float
    sample_count: int
    persona_seed: str


class DriverPerformanceEnvelope:
    """Per driver envelope that refines from the event stream.

    Thread safe. Bootstrap from a persona prior on first sight of a driver.
    Subsequent calls to `observe` move the centroid with an exponential
    moving average so the envelope tracks the driver without amplifying
    noisy single ticks. Tolerances shrink slowly as evidence accumulates.
    """

    def __init__(self, smoothing: float = 0.04, min_tolerance: float = 6.0):
        if not 0.0 < smoothing < 1.0:
            raise ValueError("smoothing must be in (0, 1)")
        if min_tolerance <= 0.0:
            raise ValueError("min_tolerance must be positive")
        self._smoothing = smoothing
        self._min_tolerance = min_tolerance
        self._centroids: Dict[str, EnvelopeCentroid] = {}
        self._lock = threading.Lock()

    def _seed_for_persona(self, driver_id: str, persona_state: str) -> EnvelopeCentroid:
        prior = PERSONA_PRIORS.get(persona_state) or PERSONA_PRIORS["Recovery"]
        means = {dim: float(prior[dim][0]) for dim in COGNITIVE_DIMENSIONS}
        tolerances = {
            dim: max(float(prior[dim][1]), self._min_tolerance) for dim in COGNITIVE_DIMENSIONS
        }
        return EnvelopeCentroid(means=means, tolerances=tolerances, sample_count=0, persona_seed=persona_state)

    def ensure(self, driver_id: str, persona_state: str = "Recovery") -> EnvelopeCentroid:
        with self._lock:
            existing = self._centroids.get(driver_id)
            if existing is not None:
                return existing
            seeded = self._seed_for_persona(driver_id, persona_state)
            self._centroids[driver_id] = seeded
            return seeded

    def observe(self, driver_id: str, state: Dict[str, float], is_fast_lap_signal: bool = True) -> EnvelopeCentroid:
        """Refine the envelope from a cognitive state.

        We only refine when `is_fast_lap_signal` is True. In V1 we use the
        confidence band as a proxy: an evaluation with a `high` band is
        treated as representative, a `moderate` band is dampened, and an
        `unstable` band is ignored. The caller decides.
        """
        persona = str(state.get("persona_state", "Recovery"))
        with self._lock:
            centroid = self._centroids.get(driver_id) or self._seed_for_persona(driver_id, persona)
            if not is_fast_lap_signal:
                self._centroids[driver_id] = centroid
                return centroid
            new_means = dict(centroid.means)
            new_tolerances = dict(centroid.tolerances)
            for dim in COGNITIVE_DIMENSIONS:
                observation = float(state.get(dim, centroid.means[dim]))
                # EMA on the mean.
                new_means[dim] = (1.0 - self._smoothing) * centroid.means[dim] + self._smoothing * observation
                # Tolerance shrinks slowly with evidence but never below the floor.
                shrink = max(0.985, 1.0 - 0.0015)
                new_tolerances[dim] = max(centroid.tolerances[dim] * shrink, self._min_tolerance)
            refined = EnvelopeCentroid(
                means=new_means,
                tolerances=new_tolerances,
                sample_count=centroid.sample_count + 1,
                persona_seed=centroid.persona_seed,
            )
            self._centroids[driver_id] = refined
            return refined

    def project(self, driver_id: str, state: Dict[str, float]) -> EnvelopeProjection:
        """Project the driver's current state against the envelope.

        Returns the centroid, the per dimension delta (current minus
        centroid, signed), and the dimension weighted Euclidean distance
        normalised by the tolerance vector. The caller turns that distance
        into seconds of lap delta or a cognitive efficiency score.
        """
        persona = str(state.get("persona_state", "Recovery"))
        centroid = self.ensure(driver_id, persona)
        deltas: Dict[str, float] = {}
        squared = 0.0
        for dim in COGNITIVE_DIMENSIONS:
            value = float(state.get(dim, centroid.means[dim]))
            delta = value - centroid.means[dim]
            normalised = delta / centroid.tolerances[dim]
            squared += DIMENSION_WEIGHTS[dim] * (normalised ** 2)
            deltas[dim] = round(delta, 3)
        distance = math.sqrt(max(squared, 0.0))
        return EnvelopeProjection(
            centroid={k: round(v, 3) for k, v in centroid.means.items()},
            tolerances={k: round(v, 3) for k, v in centroid.tolerances.items()},
            deltas=deltas,
            weighted_distance=round(distance, 4),
            sample_count=centroid.sample_count,
            persona_seed=centroid.persona_seed,
        )

    def snapshot(self) -> Dict[str, Dict[str, object]]:
        with self._lock:
            return {
                driver_id: {
                    "means": dict(centroid.means),
                    "tolerances": dict(centroid.tolerances),
                    "sample_count": centroid.sample_count,
                    "persona_seed": centroid.persona_seed,
                }
                for driver_id, centroid in self._centroids.items()
            }
