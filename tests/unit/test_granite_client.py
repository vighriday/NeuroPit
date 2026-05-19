"""Unit tests for the Granite client.

We do not call watsonx.ai during tests. The stub path is exercised directly
and the cloud path is covered with a small monkeypatched httpx client so the
expected request shape is verified without ever touching the network.
"""

from __future__ import annotations

import json
import types

import pytest

from src.backend.reasoning import granite_client
from src.backend.reasoning.granite_client import GraniteClient


class _FakeSettings:
    def __init__(self, **overrides):
        self.granite_use_stub = overrides.get("granite_use_stub", True)
        self.watsonx_api_key = overrides.get("watsonx_api_key", "")
        self.watsonx_project_id = overrides.get("watsonx_project_id", "")
        self.watsonx_url = overrides.get("watsonx_url", "https://example.invalid")
        self.granite_model_id = overrides.get("granite_model_id", "ibm/granite-3-8b-instruct")


def _state(**overrides) -> dict:
    base = {
        "driver_id": "VER",
        "stress_score": 72.0,
        "confidence_score": 58.0,
        "fatigue_score": 35.0,
        "tunnel_vision_prob": 0.0,
        "persona_state": "Aggressive",
        "confidence_band": "moderate",
    }
    base.update(overrides)
    return base


def test_stub_path_when_explicitly_requested():
    client = GraniteClient(_FakeSettings(granite_use_stub=True))
    result = client.explain(_state())
    assert result["source"] == "stub"
    assert "Aggressive" in result["text"]
    assert "moderate" in result["text"]


def test_stub_path_when_api_key_missing():
    client = GraniteClient(_FakeSettings(granite_use_stub=False, watsonx_api_key=""))
    result = client.explain(_state())
    assert result["source"] == "stub"


def test_stub_mentions_low_confidence_when_below_floor():
    client = GraniteClient(_FakeSettings(granite_use_stub=True))
    result = client.explain(_state(confidence_score=20.0))
    assert "below the strategist safety line" in result["text"]


def test_prompt_includes_reading_payload():
    prompt = GraniteClient._build_prompt(_state(), None, [])
    assert "stress_score" in prompt
    assert "VER" in prompt
    assert prompt.endswith("Explanation:")


def test_prompt_includes_grounding_when_present():
    grounding = [{"document_title": "FIA report", "snippet": "driver fatigue increases steering instability"}]
    prompt = GraniteClient._build_prompt(_state(), None, grounding)
    assert "Reference passages" in prompt
    assert "FIA report" in prompt


def test_cloud_path_uses_settings(monkeypatch):
    captured = {}

    class _FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"results": [{"generated_text": "all good", "generated_token_count": 42}]}

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            captured["client_kwargs"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["payload"] = json
            return _FakeResponse()

    monkeypatch.setattr(granite_client, "httpx", types.SimpleNamespace(Client=_FakeClient))

    client = GraniteClient(_FakeSettings(
        granite_use_stub=False,
        watsonx_api_key="secret",
        watsonx_project_id="proj-123",
    ))
    result = client.explain(_state())

    assert result["source"] == "watsonx"
    assert result["text"] == "all good"
    assert "Authorization" in captured["headers"]
    assert captured["payload"]["project_id"] == "proj-123"


def test_cloud_failure_falls_back_to_stub(monkeypatch):
    class _ExplodingClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, *args, **kwargs):
            raise RuntimeError("network down")

    monkeypatch.setattr(granite_client, "httpx", types.SimpleNamespace(Client=_ExplodingClient))

    client = GraniteClient(_FakeSettings(
        granite_use_stub=False,
        watsonx_api_key="secret",
        watsonx_project_id="proj-123",
    ))
    result = client.explain(_state())
    assert result["source"] == "stub"
