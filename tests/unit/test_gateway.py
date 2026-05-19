"""Unit tests for the FastAPI gateway.

We use the in process TestClient so we never start a real server. The Kafka
bridge is replaced by a no op for the duration of the tests, so the gateway
can boot without a broker.
"""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from src.backend.api import gateway


@pytest.fixture()
def client(monkeypatch):
    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(gateway, "_kafka_bridge", _noop)
    app = gateway.create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["service"] == "neuropit-gateway"


def test_ghost_lap_endpoint(client):
    response = client.post(
        "/ghost-lap",
        json={
            "driver_id": "VER",
            "lap_number": 12,
            "actual_lap_time_s": 92.0,
            "average_stress": 60.0,
            "average_fatigue": 30.0,
            "panic_events": 1,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["lap_number"] == 12
    assert body["ghost_lap_time_s"] < body["actual_lap_time_s"]
    assert "fear_induced_deceleration" in body["contributions"]


def test_counterfactual_endpoint_returns_known_scenario(client):
    response = client.post(
        "/counterfactual/lower_fatigue",
        json={
            "driver_id": "HAM",
            "lap_number": 30,
            "actual_lap_time_s": 91.5,
            "average_stress": 55.0,
            "average_fatigue": 60.0,
            "panic_events": 0,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["scenario"] == "lower_fatigue"
    assert "rationale" in body


def test_counterfactual_unknown_scenario_returns_404(client):
    response = client.post(
        "/counterfactual/jet_pack_mode",
        json={
            "driver_id": "HAM",
            "lap_number": 5,
            "actual_lap_time_s": 90.0,
            "average_stress": 30.0,
            "average_fatigue": 10.0,
            "panic_events": 0,
        },
    )
    assert response.status_code == 404


def test_parliament_endpoint(client):
    response = client.post(
        "/parliament",
        json={
            "driver_id": "VER",
            "stress_score": 80.0,
            "confidence_score": 30.0,
            "fatigue_score": 65.0,
            "persona_state": "Fatigue",
            "tire_wear": 0.8,
            "rain_probability": 0.2,
            "gap_to_car_ahead_s": 3.0,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["consensus"]
    assert isinstance(body["proposals"], list)
    assert len(body["proposals"]) == 7
