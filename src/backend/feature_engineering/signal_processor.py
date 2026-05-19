import numpy as np
from scipy import signal, stats
from typing import List, Dict

# Assuming models.py is reachable via this path pattern
from src.backend.ingestion.models import TelemetryFrame

class SignalProcessor:
    """
    Phase 2: Signal Intelligence & Feature Engineering.
    Calculates cognitive and behavioral features from raw telemetry windows.
    """
    
    def __init__(self, sample_rate_hz: float = 10.0):
        self.fs = sample_rate_hz

    def process_window(self, frames: List[TelemetryFrame]) -> Dict[str, float]:
        """
        Process a window of TelemetryFrames and extract intelligent features.
        """
        if not frames or len(frames) < 3:
            return {
                "steering_instability": 0.0,
                "braking_hesitation": 0.0,
                "throttle_commitment": 0.0,
                "panic_oscillation": 0.0
            }

        # Extract underlying signal arrays
        steering = np.array([f.steering_angle for f in frames])
        throttle = np.array([f.throttle for f in frames])
        brake = np.array([f.brake for f in frames])
        
        return {
            "steering_instability": self._calc_steering_instability(steering),
            "braking_hesitation": self._calc_braking_hesitation(brake),
            "throttle_commitment": self._calc_throttle_commitment(throttle),
            "panic_oscillation": self._calc_panic_oscillation(steering, brake, throttle)
        }

    def _calc_steering_instability(self, steering: np.ndarray) -> float:
        """
        Steering Instability: Uses spectral entropy of the steering signal
        to quantify chaotic or oscillatory movements.
        """
        # Fallback for small windows where PSD doesn't make sense
        if len(steering) < 10:
            return float(np.std(np.diff(steering))) if len(steering) > 1 else 0.0

        # Calculate Power Spectral Density using Welch's method
        freqs, psd = signal.welch(steering, fs=self.fs, nperseg=min(len(steering), 128))
        
        # Normalize PSD to create a pseudo-probability distribution
        psd_norm = psd / np.sum(psd) if np.sum(psd) > 0 else psd
        
        # Calculate Shannon Entropy
        entropy = stats.entropy(psd_norm + 1e-12)
        
        # Scale entropy by tracking variance to capture both frequency chaos and movement amplitude
        instability = entropy * np.var(steering)
        return float(instability)

    def _calc_braking_hesitation(self, brake: np.ndarray) -> float:
        """
        Braking Hesitation: Measures micro-adjustments or "pumping" of brakes.
        Evaluates the variance of the pedal derivative during active braking.
        """
        active_brake_idx = np.where(brake > 1.0)[0]
        if len(active_brake_idx) < 3:
            return 0.0
        
        active_brakes = brake[active_brake_idx]
        brake_diff = np.diff(active_brakes)
        
        # High variance in brake derivative implies hesitation / pumping rather than steady pressure
        return float(np.var(brake_diff))

    def _calc_throttle_commitment(self, throttle: np.ndarray) -> float:
        """
        Throttle Commitment / Aggression: Evaluates how decisively the driver accelerates.
        Determined by the maximum positive gradient of throttle application.
        """
        if len(throttle) < 2:
            return 0.0
        
        throttle_diff = np.diff(throttle)
        positive_diffs = throttle_diff[throttle_diff > 0]
        
        if len(positive_diffs) == 0:
            return 0.0
            
        aggression = np.max(positive_diffs)
        return float(aggression)

    def _calc_panic_oscillation(self, steering: np.ndarray, brake: np.ndarray, throttle: np.ndarray) -> float:
        """
        Panic Oscillation Signatures: Detects rapid corrections (zero-crossings in steering velocity)
        combined with anomalous, overlapping pedal inputs.
        """
        if len(steering) < 2:
            return 0.0
            
        steering_vel = np.diff(steering)
        
        # Find zero crossings in steering velocity (rapid changes in steering direction)
        zero_crossings = np.where(np.diff(np.signbit(steering_vel)))[0]
        zcr = len(zero_crossings) / len(steering_vel)
        
        # Penalize simultaneous pedal activity (throttle and brake both active over 5%)
        overlap_ratio = np.sum((throttle > 5) & (brake > 5)) / len(throttle)
        
        # High ZCR combined with pedal overlap correlates highly with panic / loss of control
        panic_score = (zcr * 10.0) + (overlap_ratio * 20.0)
        return float(panic_score)
