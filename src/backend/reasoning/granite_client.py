"""Thin client around IBM watsonx.ai Granite models.

Two code paths live here. The first one talks to watsonx.ai through the
public REST endpoint when an API key and project id are configured. The
second one is a local stub that produces a templated explanation built from
the same numerical inputs. The stub exists so the dashboard always has
something coherent to show, even when the cloud is unreachable.

Both paths return a dictionary with the same shape:

```
{
  "text": str,
  "source": "watsonx" | "stub",
  "model": str,
  "tokens": int | None
}
```

That contract is the only thing downstream code is allowed to depend on.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

import httpx

from src.backend.config import get_settings

logger = logging.getLogger(__name__)


class GraniteClient:
    """Calls IBM Granite, or returns a local stub when the cloud is offline."""

    def __init__(self, settings_obj=None):
        self.settings = settings_obj or get_settings()

    def explain(self, cognitive_state: dict, prompt_hint: Optional[str] = None) -> dict:
        if self.settings.granite_use_stub or not self.settings.watsonx_api_key:
            return self._stub_explanation(cognitive_state, prompt_hint)

        try:
            return self._call_watsonx(cognitive_state, prompt_hint)
        except Exception as exc:
            logger.warning("Granite cloud call failed, falling back to stub: %s", exc)
            return self._stub_explanation(cognitive_state, prompt_hint)

    def _stub_explanation(self, state: dict, prompt_hint: Optional[str]) -> dict:
        stress = float(state.get("stress_score", 0.0))
        confidence = float(state.get("confidence_score", 0.0))
        fatigue = float(state.get("fatigue_score", 0.0))
        persona = state.get("persona_state", "Recovery")
        band = state.get("confidence_band", "moderate")

        bits = []
        if stress >= 75:
            bits.append("stress is elevated")
        elif stress >= 50:
            bits.append("stress is climbing but contained")
        else:
            bits.append("stress is within baseline")

        if confidence < 40:
            bits.append("confidence has dropped below the strategist safety line")
        elif confidence < 70:
            bits.append("confidence is steady but not commanding")
        else:
            bits.append("confidence is intact")

        if fatigue >= 60:
            bits.append("fatigue is accumulating noticeably")
        elif fatigue >= 30:
            bits.append("fatigue is building gradually")
        else:
            bits.append("fatigue remains low")

        narrative = (
            f"The driver is currently in {persona} mode. "
            + ", ".join(bits)
            + f". This reading carries a {band} confidence band."
        )
        if prompt_hint:
            narrative += f" Context note: {prompt_hint}."

        return {
            "text": narrative,
            "source": "stub",
            "model": "neuropit-granite-stub",
            "tokens": None,
        }

    def _call_watsonx(self, state: dict, prompt_hint: Optional[str]) -> dict:
        endpoint = self.settings.watsonx_url.rstrip("/") + "/ml/v1/text/generation?version=2024-05-01"
        prompt = self._build_prompt(state, prompt_hint)

        payload = {
            "model_id": self.settings.granite_model_id,
            "project_id": self.settings.watsonx_project_id,
            "input": prompt,
            "parameters": {
                "decoding_method": "greedy",
                "max_new_tokens": 200,
                "min_new_tokens": 40,
                "stop_sequences": ["\n\n"],
            },
        }

        headers = {
            "Authorization": f"Bearer {self.settings.watsonx_api_key}",
            "Content-Type": "application/json",
        }

        with httpx.Client(timeout=10.0) as client:
            response = client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()

        text = ""
        if "results" in body and body["results"]:
            text = body["results"][0].get("generated_text", "").strip()
        if not text:
            raise RuntimeError("watsonx returned an empty completion")

        return {
            "text": text,
            "source": "watsonx",
            "model": self.settings.granite_model_id,
            "tokens": body.get("results", [{}])[0].get("generated_token_count"),
        }

    @staticmethod
    def _build_prompt(state: dict, prompt_hint: Optional[str]) -> str:
        cleaned = {
            "driver_id": state.get("driver_id"),
            "stress_score": state.get("stress_score"),
            "confidence_score": state.get("confidence_score"),
            "fatigue_score": state.get("fatigue_score"),
            "tunnel_vision_prob": state.get("tunnel_vision_prob"),
            "persona_state": state.get("persona_state"),
            "confidence_band": state.get("confidence_band"),
        }
        prefix = (
            "You are NeuroPit, a trustworthy explainability assistant for a "
            "Formula racing strategist. Read the cognitive twin reading below "
            "and write one short paragraph in plain language that explains "
            "what is happening, which signals contributed, and how confident "
            "the system is in the reading. Avoid exaggeration. Avoid hedging "
            "language that obscures the call to action.\n\n"
        )
        body = "Reading: " + json.dumps(cleaned)
        suffix = f"\nContext note: {prompt_hint}" if prompt_hint else ""
        return prefix + body + suffix + "\n\nExplanation:"
