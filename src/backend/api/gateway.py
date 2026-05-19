"""Cognitive gateway over the NeuroPit Cognitive Twin Operating System.

The gateway is a surface, not a product. It exposes the Probabilistic
Cognitive Inference Engine, the Emotional State Engine, the IBM Granite
explainable cognitive reasoning layer, the Ghost Lap AI, the counterfactual
simulator, and the strategy parliament to authenticated clients. The
Mission Control surface in `src/frontend` is one of those clients. Other
trusted services (a race engineer console, a stewards review tool, a
research notebook) can read the same Cognitive Twin through the same JWT
contract.

The Kafka bridge runs as a background task. When the broker is unreachable
the gateway stays up and the dashboard sees a synthetic heartbeat so the
operator can tell the difference between a quiet race and a broken stack.

Authentication is enforced through a bearer token. In development the
default JWT secret in `.env.example` puts the gateway in anonymous mode so a
fresh checkout runs without ceremony. Setting a real secret in `.env`
immediately requires every protected route to present a bearer token.
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Set

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from src.backend.api import schemas
from src.backend.config import get_settings
from src.backend.inference.emotional_state import evaluate as evaluate_emotion
from src.backend.prescription.engine import PrescriptionEngine
from src.backend.reporting.post_race import build_report
from src.backend.security import roles as roles_registry
from src.backend.security.auth import current_claims, require_scopes
from src.backend.security.tokens import TokenClaims, issue_token
from src.backend.simulation import counterfactual as counterfactual_engine
from src.backend.simulation.ghost_lap import LapCognitiveSummary, attribute_lost_time
from src.backend.strategy import parliament
from src.backend.whatif.replay import (
    build_rationale as build_whatif_rationale,
    load_audit_window,
    replay_trajectory,
    summarise_trajectory,
)

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast(self, payload: dict) -> None:
        async with self._lock:
            dead: List[WebSocket] = []
            for connection in self._connections:
                try:
                    await connection.send_json(payload)
                except Exception:
                    dead.append(connection)
            for connection in dead:
                self._connections.discard(connection)


async def _kafka_bridge(manager: ConnectionManager) -> None:
    settings = get_settings()
    try:
        from confluent_kafka import Consumer
    except Exception as exc:
        logger.warning("confluent_kafka not available, broadcasting heartbeats only: %s", exc)
        await _heartbeat_loop(manager)
        return

    consumer = Consumer(
        {
            "bootstrap.servers": settings.kafka_broker_url,
            "group.id": "neuropit-gateway",
            "auto.offset.reset": "latest",
        }
    )
    consumer.subscribe(
        [
            "cognitive-state-inference",
            "explanation-events",
            "emotional-events",
            "anomaly-events",
            "cognitive-prescriptions",
        ]
    )

    try:
        while True:
            msg = await asyncio.to_thread(consumer.poll, 0.5)
            if msg is None:
                await asyncio.sleep(0)
                continue
            if msg.error():
                logger.warning("Gateway consumer error: %s", msg.error())
                continue
            try:
                payload = json.loads(msg.value().decode("utf-8"))
            except Exception:
                continue
            envelope = {"channel": msg.topic(), "payload": payload}
            await manager.broadcast(envelope)
    finally:
        consumer.close()


async def _heartbeat_loop(manager: ConnectionManager) -> None:
    while True:
        await manager.broadcast(
            {
                "channel": "heartbeat",
                "payload": {"timestamp": datetime.now(timezone.utc).isoformat()},
            }
        )
        await asyncio.sleep(2.0)


def _scope_dependency(*required: str):
    """Build a FastAPI dependency that wires the bearer token check to scopes."""

    def _dependency(claims: TokenClaims = Depends(current_claims)) -> TokenClaims:
        for scope in required:
            if not roles_registry.has_scope(claims.role, scope):
                raise HTTPException(
                    status_code=403,
                    detail=f"Role {claims.role!r} does not have scope {scope!r}",
                )
        return claims

    return _dependency


_PREVIEW_ENGINE = PrescriptionEngine()


def create_app() -> FastAPI:
    manager = ConnectionManager()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        tasks = [
            asyncio.create_task(_kafka_bridge(manager)),
            asyncio.create_task(_heartbeat_loop(manager)),
        ]
        try:
            yield
        finally:
            for task in tasks:
                task.cancel()
            for task in tasks:
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

    app = FastAPI(
        title="NeuroPit Cognitive Gateway",
        version="0.2.0",
        description=(
            "Real time gateway over the NeuroPit Cognitive Twin Operating System. "
            "Surfaces the probabilistic cognitive inference engine, the emotional state engine, "
            "the IBM Granite explainable cognitive reasoning layer, the Ghost Lap AI, the "
            "counterfactual simulator, and the strategy parliament to authenticated clients. "
            "Telemetry is infrastructure. Cognition is the product."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok", "service": "neuropit-gateway"}

    @app.post("/auth/token", response_model=schemas.TokenResponse)
    def mint_token(req: schemas.TokenRequest) -> schemas.TokenResponse:
        try:
            roles_registry.get_role(req.role)
        except KeyError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        token = issue_token(req.subject, req.role, req.expires_in_seconds)
        return schemas.TokenResponse(
            access_token=token,
            expires_in_seconds=req.expires_in_seconds or get_settings().api_token_expiry_minutes * 60,
            role=req.role,
        )

    @app.post("/ghost-lap", response_model=schemas.GhostLapResponse)
    def ghost_lap(
        req: schemas.LapSummaryRequest,
        _claims: TokenClaims = Depends(_scope_dependency("read:ghost_lap")),
    ) -> schemas.GhostLapResponse:
        summary = LapCognitiveSummary(
            lap_number=req.lap_number,
            driver_id=req.driver_id,
            actual_lap_time_s=req.actual_lap_time_s,
            average_stress=req.average_stress,
            average_fatigue=req.average_fatigue,
            panic_events=req.panic_events,
        )
        result = attribute_lost_time(summary)
        return schemas.GhostLapResponse(
            driver_id=result.driver_id,
            lap_number=result.lap_number,
            actual_lap_time_s=result.actual_lap_time_s,
            ghost_lap_time_s=result.ghost_lap_time_s,
            lost_time_s=result.lost_time_s,
            contributions=result.contributions,
        )

    @app.post("/counterfactual/{scenario}", response_model=schemas.CounterfactualResponse)
    def counterfactual(
        scenario: str,
        req: schemas.LapSummaryRequest,
        _claims: TokenClaims = Depends(_scope_dependency("write:counterfactual")),
    ) -> schemas.CounterfactualResponse:
        if scenario not in counterfactual_engine.SCENARIOS:
            raise HTTPException(status_code=404, detail=f"Unknown scenario {scenario!r}")
        summary = LapCognitiveSummary(
            lap_number=req.lap_number,
            driver_id=req.driver_id,
            actual_lap_time_s=req.actual_lap_time_s,
            average_stress=req.average_stress,
            average_fatigue=req.average_fatigue,
            panic_events=req.panic_events,
        )
        result = counterfactual_engine.run_scenario(scenario, summary)
        return schemas.CounterfactualResponse(
            scenario=result.scenario,
            baseline_lap_time_s=result.baseline_lap_time_s,
            counterfactual_lap_time_s=result.counterfactual_lap_time_s,
            lap_delta_s=result.lap_delta_s,
            rationale=result.rationale,
            adjustments=result.adjustments,
        )

    @app.post("/parliament", response_model=schemas.ParliamentResponse)
    def parliament_endpoint(
        req: schemas.ParliamentRequest,
        _claims: TokenClaims = Depends(_scope_dependency("read:strategy")),
    ) -> schemas.ParliamentResponse:
        report = parliament.convene(req.model_dump())
        return schemas.ParliamentResponse(
            consensus=report.consensus,
            consensus_confidence=report.consensus_confidence,
            margin_over_runner_up=report.margin_over_runner_up,
            tally=report.tally,
            proposals=[
                schemas.ParliamentProposal(
                    agent=p.agent,
                    proposal=p.proposal,
                    confidence=p.confidence,
                    rationale=p.rationale,
                )
                for p in report.proposals
            ],
            transcript=report.transcript,
        )

    @app.post("/emotional", response_model=schemas.EmotionalEvaluationResponse)
    def emotional_endpoint(
        req: schemas.EmotionalEvaluationRequest,
        _claims: TokenClaims = Depends(_scope_dependency("read:cognitive")),
    ) -> schemas.EmotionalEvaluationResponse:
        report = evaluate_emotion(
            cognitive_state=req.cognitive_state,
            features=req.features,
            biometrics=req.biometrics,
        )
        return schemas.EmotionalEvaluationResponse(
            driver_id=report.driver_id or req.cognitive_state.get("driver_id", ""),
            timestamp=report.timestamp or req.cognitive_state.get("timestamp", ""),
            distribution=report.distribution,
            dominant_emotion=report.dominant_emotion,
            dominant_probability=report.dominant_probability,
        )

    @app.post("/prescription/preview", response_model=schemas.PrescriptionResponse)
    def prescription_preview(
        req: schemas.PrescriptionPreviewRequest,
        _claims: TokenClaims = Depends(_scope_dependency("write:prescription_preview")),
    ) -> schemas.PrescriptionResponse:
        result = _PREVIEW_ENGINE.emit(state=req.cognitive_state, forecast=req.forecast)
        data = result.to_dict()
        return schemas.PrescriptionResponse(
            driver_id=str(data["driver_id"]),
            timestamp=str(data["timestamp"]),
            optimality=data["optimality"],
            primary=data["primary"],
            alternatives=data["alternatives"],
            rationale=str(data["rationale"]),
            forecast_used=bool(data["forecast_used"]),
            granite=None,
        )

    @app.post("/whatif/replay", response_model=schemas.WhatIfReplayResponse)
    def whatif_replay(
        req: schemas.WhatIfReplayRequest,
        _claims: TokenClaims = Depends(_scope_dependency("write:whatif")),
    ) -> schemas.WhatIfReplayResponse:
        rows = load_audit_window(
            driver_id=req.driver_id,
            window_seconds=req.window_seconds,
            audit_path=req.audit_path,
        )
        if not rows:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"No audit rows found for driver {req.driver_id!r} in "
                    f"the requested window."
                ),
            )
        mutations = [m.model_dump() for m in req.mutations]
        trajectory = replay_trajectory(rows, mutations)
        summary = summarise_trajectory(trajectory)
        rationale = build_whatif_rationale(summary, mutations)
        trajectory_payload = [
            schemas.WhatIfTrajectoryPoint(
                timestamp=p.timestamp,
                baseline={k: float(v) for k, v in p.baseline.items() if isinstance(v, (int, float))},
                counterfactual={k: float(v) for k, v in p.counterfactual.items() if isinstance(v, (int, float))},
                delta={k: float(v) for k, v in p.delta.items() if isinstance(v, (int, float))},
            )
            for p in trajectory
        ]
        return schemas.WhatIfReplayResponse(
            driver_id=req.driver_id,
            window_seconds=req.window_seconds,
            mutations=mutations,
            baseline_count=len(rows),
            trajectory=trajectory_payload,
            summary=summary,
            rationale=rationale,
        )

    @app.get("/reports/{session_id}", response_model=schemas.PostRaceReportResponse)
    def post_race_report(
        session_id: str,
        _claims: TokenClaims = Depends(_scope_dependency("read:audit")),
    ) -> schemas.PostRaceReportResponse:
        normalised = None if session_id in {"_all", "all"} else session_id
        report = build_report(normalised)
        return schemas.PostRaceReportResponse(**report)

    @app.websocket("/ws/cognitive")
    async def cognitive_socket(websocket: WebSocket) -> None:
        await manager.connect(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            await manager.disconnect(websocket)

    return app


app = create_app()


def main() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "src.backend.api.gateway:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
