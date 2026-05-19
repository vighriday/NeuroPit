"""Unit tests for the FastAPI gateway.

Uses the in process TestClient so we never start a real server. The Kafka
bridge is replaced by a no op for the duration of the tests, so the gateway
can boot without a broker. JWT enforcement is exercised through the
token endpoint and the bearer header.
"""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from src.backend.api import gateway
from src.backend.config import get_settings


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    monkeypatch.setenv("API_JWT_SECRET", "gateway-test-secret")
    monkeypatch.setenv("API_JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("API_TOKEN_EXPIRY_MINUTES", "5")
    get_settings.cache_clear()  # type: ignore[attr-defined]
    yield
    get_settings.cache_clear()  # type: ignore[attr-defined]


@pytest.fixture()
def client(monkeypatch):
    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(gateway, "_kafka_bridge", _noop)
    app = gateway.create_app()
    with TestClient(app) as test_client:
        yield test_client


def _token(client: TestClient, role: str) -> str:
    response = client.post("/auth/token", json={"subject": f"test-{role}", "role": role})
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth(role_token: str) -> dict:
    return {"Authorization": f"Bearer {role_token}"}


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["service"] == "neuropit-gateway"


def test_token_endpoint_rejects_unknown_role(client):
    response = client.post("/auth/token", json={"subject": "anyone", "role": "ceo"})
    assert response.status_code == 400


def test_ghost_lap_endpoint(client):
    token = _token(client, "driver_engineer")
    response = client.post(
        "/ghost-lap",
        headers=_auth(token),
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
    token = _token(client, "race_strategist")
    response = client.post(
        "/counterfactual/lower_fatigue",
        headers=_auth(token),
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
    token = _token(client, "race_strategist")
    response = client.post(
        "/counterfactual/jet_pack_mode",
        headers=_auth(token),
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


def test_counterfactual_role_without_scope_is_forbidden(client):
    token = _token(client, "neuro_analyst")
    response = client.post(
        "/counterfactual/lower_fatigue",
        headers=_auth(token),
        json={
            "driver_id": "HAM",
            "lap_number": 30,
            "actual_lap_time_s": 91.5,
            "average_stress": 55.0,
            "average_fatigue": 60.0,
            "panic_events": 0,
        },
    )
    assert response.status_code == 403


def test_parliament_endpoint(client):
    token = _token(client, "race_strategist")
    response = client.post(
        "/parliament",
        headers=_auth(token),
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


def test_parliament_requires_bearer_token(client):
    response = client.post(
        "/parliament",
        json={
            "driver_id": "VER",
            "stress_score": 50.0,
            "confidence_score": 50.0,
            "fatigue_score": 20.0,
        },
    )
    assert response.status_code == 401


def test_emotional_endpoint(client):
    token = _token(client, "neuro_analyst")
    response = client.post(
        "/emotional",
        headers=_auth(token),
        json={
            "cognitive_state": {
                "driver_id": "VER",
                "timestamp": "2026-05-19T12:00:00Z",
                "stress_score": 65.0,
                "confidence_score": 55.0,
                "fatigue_score": 30.0,
                "panic_probability": 22.0,
                "tunnel_vision_prob": 0.0,
                "cognitive_load_score": 50.0,
                "persona_state": "Aggressive",
            },
            "features": {"throttle_commitment": 70.0, "panic_oscillation": 8.0, "braking_hesitation": 400.0},
            "biometrics": {"synthetic_hrv": 35.0},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["driver_id"] == "VER"
    assert body["dominant_emotion"] in {
        "confidence",
        "fear",
        "panic",
        "frustration",
        "aggression",
        "recovery",
        "overconfidence",
        "hesitation",
        "caution",
    }
    assert 0.0 <= body["dominant_probability"] <= 1.0


def test_reports_endpoint_returns_envelope(client, tmp_path, monkeypatch):
    monkeypatch.setenv("AUDIT_LOG_DIR", str(tmp_path))
    get_settings.cache_clear()  # type: ignore[attr-defined]
    token = _token(client, "neuro_analyst")
    response = client.get("/reports/all", headers=_auth(token))
    assert response.status_code == 200
    body = response.json()
    assert body["driver_count"] == 0
    assert body["drivers"] == {}
