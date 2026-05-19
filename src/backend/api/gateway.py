"""FastAPI gateway between the cognitive pipeline and the dashboard.

Exposes a small REST surface for the Ghost Lap, counterfactual, and
parliament endpoints, plus a single WebSocket channel that fans out the
cognitive state stream and the Granite explanations to the Next.js Mission
Control dashboard.

The Kafka bridge runs as a background task. When the broker is unreachable
the gateway stays up and the dashboard sees a synthetic heartbeat so the
operator can tell the difference between a quiet race and a broken stack.
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Set

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from src.backend.api import schemas
from src.backend.config import get_settings
from src.backend.simulation import counterfactual as counterfactual_engine
from src.backend.simulation.ghost_lap import LapCognitiveSummary, attribute_lost_time
from src.backend.strategy import parliament

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
    """Forward cognitive and explanation events from Kafka to the dashboard."""
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
    consumer.subscribe(["cognitive-state-inference", "explanation-events"])

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
            envelope = {
                "channel": msg.topic(),
                "payload": payload,
            }
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


def create_app() -> FastAPI:
    manager = ConnectionManager()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task = asyncio.create_task(_kafka_bridge(manager))
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    app = FastAPI(
        title="NeuroPit Gateway",
        version="0.1.0",
        description="Bridge between the cognitive pipeline and the Mission Control dashboard.",
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

    @app.post("/ghost-lap", response_model=schemas.GhostLapResponse)
    def ghost_lap(req: schemas.LapSummaryRequest) -> schemas.GhostLapResponse:
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
    def counterfactual(scenario: str, req: schemas.LapSummaryRequest) -> schemas.CounterfactualResponse:
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
    def parliament_endpoint(req: schemas.ParliamentRequest) -> schemas.ParliamentResponse:
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
