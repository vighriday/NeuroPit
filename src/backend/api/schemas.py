"""Pydantic schemas for the FastAPI gateway.

Every payload that crosses the network has a stable shape declared here so
the Next.js dashboard can be generated against a real contract instead of
fishing for fields at runtime.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CognitiveSnapshot(BaseModel):
    driver_id: str
    timestamp: str
    stress_score: float = Field(ge=0.0, le=100.0)
    confidence_score: float = Field(ge=0.0, le=100.0)
    fatigue_score: float = Field(ge=0.0, le=100.0)
    cognitive_load_score: float = Field(default=0.0, ge=0.0, le=100.0)
    attention_stability: float = Field(default=0.0, ge=0.0, le=100.0)
    strategic_reliability: float = Field(default=0.0, ge=0.0, le=100.0)
    panic_probability: float = Field(default=0.0, ge=0.0, le=100.0)
    emotional_drift_score: float = Field(default=0.0, ge=0.0, le=100.0)
    tunnel_vision_prob: float = Field(ge=0.0, le=100.0)
    persona_state: str
    confidence_band: str


class ExplanationPayload(BaseModel):
    text: str
    source: str
    model: str
    tokens: Optional[int] = None
    grounding: List[Dict[str, Any]] = Field(default_factory=list)


class ExplanationEvent(BaseModel):
    driver_id: str
    timestamp: str
    state: CognitiveSnapshot
    explanation: ExplanationPayload


class LapSummaryRequest(BaseModel):
    driver_id: str
    lap_number: int
    actual_lap_time_s: float = Field(gt=0.0)
    average_stress: float = Field(ge=0.0, le=100.0)
    average_fatigue: float = Field(ge=0.0, le=100.0)
    panic_events: int = Field(ge=0)


class GhostLapResponse(BaseModel):
    driver_id: str
    lap_number: int
    actual_lap_time_s: float
    ghost_lap_time_s: float
    lost_time_s: float
    contributions: Dict[str, float]


class CounterfactualResponse(BaseModel):
    scenario: str
    baseline_lap_time_s: float
    counterfactual_lap_time_s: float
    lap_delta_s: float
    rationale: str
    adjustments: Dict[str, float]


class ParliamentRequest(BaseModel):
    driver_id: str
    stress_score: float
    confidence_score: float
    fatigue_score: float
    persona_state: str = "Recovery"
    tire_wear: float = 0.5
    rain_probability: float = 0.0
    gap_to_car_ahead_s: float = 99.0


class ParliamentProposal(BaseModel):
    agent: str
    proposal: str
    confidence: float
    rationale: str


class ParliamentResponse(BaseModel):
    consensus: str
    consensus_confidence: float
    margin_over_runner_up: float
    tally: Dict[str, float]
    proposals: List[ParliamentProposal]
    transcript: str


class EmotionalEvaluationRequest(BaseModel):
    cognitive_state: Dict[str, Any]
    features: Dict[str, Any] = Field(default_factory=dict)
    biometrics: Dict[str, Any] = Field(default_factory=dict)


class EmotionalEvaluationResponse(BaseModel):
    driver_id: str
    timestamp: str
    distribution: Dict[str, float]
    dominant_emotion: str
    dominant_probability: float


class PostRaceReportResponse(BaseModel):
    session_id: Optional[str] = None
    generated_on: str
    driver_count: int
    total_evaluations: int
    drivers: Dict[str, Any]


class TokenRequest(BaseModel):
    subject: str
    role: str
    expires_in_seconds: Optional[int] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    role: str


class PrescriptionPreviewRequest(BaseModel):
    """Ad hoc preview of the prescriptive engine without going through Kafka."""

    cognitive_state: Dict[str, Any]
    forecast: Optional[Dict[str, Any]] = None


class PrescriptionResponse(BaseModel):
    driver_id: str
    timestamp: str
    optimality: Dict[str, Any]
    primary: Dict[str, Any]
    alternatives: List[Dict[str, Any]] = Field(default_factory=list)
    rationale: str
    forecast_used: bool
    granite: Optional[Dict[str, Any]] = None


class WhatIfMutation(BaseModel):
    """One mutation to apply to a recorded cognitive event during replay."""

    target: str = Field(description="Dotted path inside the audit record to override.")
    value: Any = Field(description="Replacement value. Numbers and strings supported.")


class WhatIfReplayRequest(BaseModel):
    driver_id: str
    audit_path: Optional[str] = Field(
        default=None,
        description="Absolute or relative path to an audit JSONL file. Defaults to today's file.",
    )
    window_seconds: int = Field(default=20, ge=1, le=600)
    mutations: List[WhatIfMutation] = Field(default_factory=list)


class WhatIfTrajectoryPoint(BaseModel):
    timestamp: str
    baseline: Dict[str, float]
    counterfactual: Dict[str, float]
    delta: Dict[str, float]


class WhatIfReplayResponse(BaseModel):
    driver_id: str
    window_seconds: int
    mutations: List[Dict[str, Any]]
    baseline_count: int
    trajectory: List[WhatIfTrajectoryPoint]
    summary: Dict[str, Any]
    rationale: str
