"""Unit tests for the Granite client.

We never download model weights and we never touch watsonx.ai during the unit
suite. The local inference path is exercised through a monkeypatched
pipeline loader. The watsonx path is exercised through a monkeypatched
httpx client. The stub path is exercised directly.
"""

from __future__ import annotations

import types

import pytest

from src.backend.reasoning import granite_client
from src.backend.reasoning.granite_client import GraniteClient


class _FakeSettings:
    def __init__(self, **overrides):
        self.granite_use_stub = overrides.get("granite_use_stub", False)
        self.granite_use_local = overrides.get("granite_use_local", True)
        self.watsonx_api_key = overrides.get("watsonx_api_key", "")
        self.watsonx_project_id = overrides.get("watsonx_project_id", "")
        self.watsonx_url = overrides.get("watsonx_url", "https://example.invalid")
        self.granite_model_id = overrides.get(
            "granite_model_id", "ibm-granite/granite-3.1-8b-instruct"
        )


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


@pytest.fixture(autouse=True)
def _clear_pipeline_cache():
    granite_client._PIPELINE_CACHE.clear()
    yield
    granite_client._PIPELINE_CACHE.clear()


# ---------------------------------------------------------------------------
# Stub path
# ---------------------------------------------------------------------------


def test_stub_path_when_explicitly_requested():
    client = GraniteClient(_FakeSettings(granite_use_stub=True, granite_use_local=False))
    result = client.explain(_state())
    assert result["source"] == "stub"
    assert "Aggressive" in result["text"]
    assert "moderate" in result["text"]


def test_stub_mentions_low_confidence_when_below_floor():
    client = GraniteClient(_FakeSettings(granite_use_stub=True, granite_use_local=False))
    result = client.explain(_state(confidence_score=20.0))
    assert "below the strategist safety line" in result["text"]


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Local Hugging Face path
# ---------------------------------------------------------------------------


class _FakeTokenizer:
    eos_token_id = 0

    def encode(self, text: str):
        return [1] * max(1, len(text.split()))


class _FakeGenerator:
    def __init__(self, output_text: str):
        self.output_text = output_text
        self.tokenizer = _FakeTokenizer()
        self.calls = []

    def __call__(self, prompt, **kwargs):
        self.calls.append({"prompt": prompt, **kwargs})
        return [{"generated_text": prompt + self.output_text}]


def test_local_path_uses_pipeline(monkeypatch):
    fake = _FakeGenerator("Driver stress is climbing because steering instability spiked over six laps.")
    monkeypatch.setattr(granite_client, "_load_local_pipeline", lambda _model: fake)

    client = GraniteClient(_FakeSettings(granite_use_stub=False, granite_use_local=True))
    result = client.explain(_state())

    assert result["source"] == "granite-local"
    assert result["model"] == "ibm-granite/granite-3.1-8b-instruct"
    assert "steering instability" in result["text"]
    assert fake.calls, "pipeline should have been called"


def test_local_failure_falls_back_to_stub(monkeypatch):
    def _explode(_model):
        raise RuntimeError("model download failed")

    monkeypatch.setattr(granite_client, "_load_local_pipeline", _explode)

    client = GraniteClient(_FakeSettings(granite_use_stub=False, granite_use_local=True))
    result = client.explain(_state())
    assert result["source"] == "stub"


def test_local_falls_through_to_watsonx_when_disabled(monkeypatch):
    captured = {}

    class _FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"results": [{"generated_text": "all good", "generated_token_count": 42}]}

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            captured["kwargs"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers=None, json=None):
            captured["payload"] = json
            return _FakeResponse()

    monkeypatch.setattr(granite_client, "httpx", types.SimpleNamespace(Client=_FakeClient))

    client = GraniteClient(_FakeSettings(
        granite_use_stub=False,
        granite_use_local=False,
        watsonx_api_key="secret",
        watsonx_project_id="proj-123",
    ))
    result = client.explain(_state())

    assert result["source"] == "watsonx"
    assert result["text"] == "all good"
    assert captured["payload"]["project_id"] == "proj-123"


def test_watsonx_failure_falls_back_to_stub(monkeypatch):
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
        granite_use_local=False,
        watsonx_api_key="secret",
        watsonx_project_id="proj-123",
    ))
    result = client.explain(_state())
    assert result["source"] == "stub"


def test_no_credentials_lands_on_stub(monkeypatch):
    client = GraniteClient(_FakeSettings(
        granite_use_stub=False,
        granite_use_local=False,
        watsonx_api_key="",
        watsonx_project_id="",
    ))
    result = client.explain(_state())
    assert result["source"] == "stub"
