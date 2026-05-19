"""Behavioural feature engine.

Turns a sliding window of telemetry frames into the behavioural feature
vector consumed by the cognitive engine. The features are documented in
`docs/COGNITIVE_METHODOLOGY.md` and listed in PRD section fourteen.

The processor is deliberately stateless across windows. The pipeline that
calls it owns the per driver buffer.
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np
from scipy import signal, stats

from src.backend.ingestion.models import TelemetryFrame


EMPTY_FEATURES: Dict[str, float] = {
    "steering_instability": 0.0,
    "braking_hesitation": 0.0,
    "throttle_commitment": 0.0,
    "panic_oscillation": 0.0,
    "line_consistency": 50.0,
    "reaction_smoothness": 50.0,
}


class SignalProcessor:
    def __init__(self, sample_rate_hz: float = 10.0):
        self.fs = sample_rate_hz

    def process_window(self, frames: List[TelemetryFrame]) -> Dict[str, float]:
        if not frames or len(frames) < 3:
            return dict(EMPTY_FEATURES)

        steering = np.array([f.steering_angle for f in frames])
        throttle = np.array([f.throttle for f in frames])
        brake = np.array([f.brake for f in frames])
        speed = np.array([f.speed for f in frames])
        positions = np.array([[f.x, f.y] for f in frames])

        return {
            "steering_instability": self._calc_steering_instability(steering),
            "braking_hesitation": self._calc_braking_hesitation(brake),
            "throttle_commitment": self._calc_throttle_commitment(throttle),
            "panic_oscillation": self._calc_panic_oscillation(steering, brake, throttle),
            "line_consistency": self._calc_line_consistency(positions),
            "reaction_smoothness": self._calc_reaction_smoothness(speed, throttle, brake),
        }

    def _calc_steering_instability(self, steering: np.ndarray) -> float:
        """Spectral entropy of the steering signal weighted by variance."""
        if len(steering) < 10:
            return float(np.std(np.diff(steering))) if len(steering) > 1 else 0.0

        _freqs, psd = signal.welch(steering, fs=self.fs, nperseg=min(len(steering), 128))
        psd_norm = psd / np.sum(psd) if np.sum(psd) > 0 else psd
        entropy = stats.entropy(psd_norm + 1e-12)
        instability = entropy * np.var(steering)
        return float(instability)

    def _calc_braking_hesitation(self, brake: np.ndarray) -> float:
        """Variance of the brake derivative during active braking."""
        active_brake_idx = np.where(brake > 1.0)[0]
        if len(active_brake_idx) < 3:
            return 0.0

        active_brakes = brake[active_brake_idx]
        brake_diff = np.diff(active_brakes)
        return float(np.var(brake_diff))

    def _calc_throttle_commitment(self, throttle: np.ndarray) -> float:
        """Maximum positive throttle gradient inside the window."""
        if len(throttle) < 2:
            return 0.0

        throttle_diff = np.diff(throttle)
        positive_diffs = throttle_diff[throttle_diff > 0]
        if len(positive_diffs) == 0:
            return 0.0
        return float(np.max(positive_diffs))

    def _calc_panic_oscillation(self, steering: np.ndarray, brake: np.ndarray, throttle: np.ndarray) -> float:
        """Steering zero crossing rate combined with simultaneous pedal use."""
        if len(steering) < 2:
            return 0.0

        steering_vel = np.diff(steering)
        zero_crossings = np.where(np.diff(np.signbit(steering_vel)))[0]
        zcr = len(zero_crossings) / len(steering_vel)

        overlap_ratio = float(np.sum((throttle > 5) & (brake > 5))) / len(throttle)
        panic_score = (zcr * 10.0) + (overlap_ratio * 20.0)
        return float(panic_score)

    def _calc_line_consistency(self, positions: np.ndarray) -> float:
        """Lap on lap tracing precision proxy from positional jitter.

        We do not have an authoritative reference line in the streaming
        window, so we approximate consistency from the smoothness of the
        positional path. A smooth path returns a high score, a jagged
        path returns a low score. Scaled to zero to one hundred.
        """
        if positions.shape[0] < 3 or positions.shape[1] != 2:
            return 50.0

        differences = np.diff(positions, axis=0)
        magnitudes = np.linalg.norm(differences, axis=1)
        if len(magnitudes) < 2 or np.mean(magnitudes) == 0.0:
            return 100.0

        coefficient_of_variation = float(np.std(magnitudes) / max(np.mean(magnitudes), 1e-6))
        score = 100.0 * np.exp(-coefficient_of_variation)
        return float(max(0.0, min(100.0, score)))

    def _calc_reaction_smoothness(
        self,
        speed: np.ndarray,
        throttle: np.ndarray,
        brake: np.ndarray,
    ) -> float:
        """Reaction smoothness index.

        Looks at how quickly the driver transitions between throttle and
        brake when the speed signal indicates a corner approach. A smooth
        driver decelerates with a single brake application and accelerates
        with a single throttle ramp. A jerky driver toggles repeatedly.
        Scaled to zero to one hundred.
        """
        if len(speed) < 4:
            return 50.0

        speed_diff = np.diff(speed)
        decelerating = speed_diff < -0.5
        accelerating = speed_diff > 0.5

        decel_pedal_use = np.sum(throttle[:-1][decelerating] > 20.0)
        accel_pedal_use = np.sum(brake[:-1][accelerating] > 20.0)
        conflict = decel_pedal_use + accel_pedal_use

        smoothness = 100.0 - min(conflict * 6.0, 100.0)
        return float(smoothness)
