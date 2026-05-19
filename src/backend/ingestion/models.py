"""Core domain models shared across every NeuroPit worker.

These are the data shapes referenced by PRD section forty. Keeping them in
one module means every downstream service speaks the same vocabulary and a
new contributor can read the data flow without chasing definitions.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DriverInfo(BaseModel):
    driver_id: str = Field(..., description="Unique driver identifier (for example VER, HAM)")
    team: str = Field(..., description="Constructor team name")
    full_name: Optional[str] = None


class Race(BaseModel):
    race_id: str = Field(..., description="Stable identifier for the race weekend, for example 2021_AbuDhabi")
    year: int
    event: str = Field(..., description="Human readable event name")
    circuit: Optional[str] = None
    country: Optional[str] = None


class Session(BaseModel):
    session_id: str = Field(..., description="Combination of race id and session code, for example 2021_AbuDhabi_R")
    race_id: str
    session_code: str = Field(..., description="FastF1 session code, for example R, Q, FP1")
    start_time: Optional[datetime] = None
    drivers: List[str] = Field(default_factory=list)


class TelemetryFrame(BaseModel):
    timestamp: datetime = Field(..., description="Exact time of the telemetry reading")
    driver_id: str = Field(..., description="Link to the driver")
    session_id: str = Field(..., description="Identifier for the race or session")

    speed: float = Field(..., description="Speed in km/h")
    rpm: int = Field(..., description="Engine RPM")
    gear: int = Field(..., description="Current gear")
    throttle: float = Field(..., description="Throttle pressure percentage zero to one hundred")
    brake: float = Field(..., description="Brake pressure percentage or binary flag depending on data source")

    steering_angle: float = Field(default=0.0, description="Steering wheel angle")
    drs: int = Field(default=0, description="DRS activation status, FastF1 codes")

    x: float = Field(..., description="X coordinate on track map")
    y: float = Field(..., description="Y coordinate on track map")
    z: float = Field(..., description="Z coordinate on track map")

    status: str = Field(default="OnTrack", description="Track status")


class RaceEvent(BaseModel):
    timestamp: datetime
    event_type: str = Field(..., description="Type of event such as lap complete, incident, pit")
    driver_id: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class CognitiveState(BaseModel):
    """Full cognitive twin payload emitted by the inference engine."""

    driver_id: str
    timestamp: str
    stress_score: float = Field(ge=0.0, le=100.0)
    confidence_score: float = Field(ge=0.0, le=100.0)
    fatigue_score: float = Field(ge=0.0, le=100.0)
    cognitive_load_score: float = Field(ge=0.0, le=100.0)
    attention_stability: float = Field(ge=0.0, le=100.0)
    strategic_reliability: float = Field(ge=0.0, le=100.0)
    panic_probability: float = Field(ge=0.0, le=100.0)
    emotional_drift_score: float = Field(ge=0.0, le=100.0)
    tunnel_vision_prob: float = Field(ge=0.0, le=100.0)
    persona_state: str
    confidence_band: str


class EmotionalState(BaseModel):
    """Emotional state distribution emitted by the emotional engine."""

    driver_id: str
    timestamp: str
    distribution: Dict[str, float]
    dominant_emotion: str
    dominant_probability: float


class StrategyRecommendation(BaseModel):
    """Final strategist facing recommendation produced by the parliament."""

    driver_id: str
    timestamp: str
    consensus: str
    consensus_confidence: float = Field(ge=0.0, le=1.0)
    margin_over_runner_up: float
    tally: Dict[str, float]
    rationale: str


class Simulation(BaseModel):
    """A single counterfactual or what if scenario result."""

    scenario: str
    driver_id: str
    lap_number: int
    baseline_lap_time_s: float
    counterfactual_lap_time_s: float
    lap_delta_s: float
    rationale: str
    adjustments: Dict[str, float]


class ConfidenceReport(BaseModel):
    """Lightweight wrapper around the trust band attached to any emission."""

    band: str
    data_completeness: float = Field(ge=0.0, le=1.0)
    sensor_agreement: float = Field(ge=0.0, le=1.0)
