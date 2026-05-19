"""IBM Granite explainable cognitive reasoning client.

This module is the bridge between the probabilistic Cognitive Twin and the
human readable explanation a strategist sees on the Mission Control surface.

Three code paths live here. The order they are tried is also the order they
should be preferred at runtime.

1. Local Hugging Face Granite. Loads `ibm-granite/granite-3.1-8b-instruct`
   (or any model id set through `GRANITE_MODEL_ID`) through the
   `transformers` library and runs inference locally. No API key. No
   network. This is the path the open source community in
   `https://github.com/ibm-granite-community` actively supports.
2. IBM watsonx.ai cloud. Only used when `WATSONX_API_KEY` and
   `WATSONX_PROJECT_ID` are present. Useful when a teammate already has a
   watsonx project and wants to keep the inference cost off the laptop.
3. Templated local stub. Pure Python. Always available. The Mission Control
   surface never goes dark.

Every path returns the same dictionary shape:

```
{
  "text": str,
  "source": "granite-local" | "watsonx" | "stub",
  "model": str,
  "tokens": int | None,
  "grounding": list[dict]
}
```

Downstream code is only allowed to depend on that contract.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import List, Optional

import httpx

from src.backend.config import get_settings

logger = logging.getLogger(__name__)


_PIPELINE_LOCK = threading.Lock()
_PIPELINE_CACHE: dict = {}


def _load_local_pipeline(model_id: str):
    """Lazily load the Hugging Face Granite pipeline.

    Cached per model id so repeated calls re use the same in memory model.
    """
    cached = _PIPELINE_CACHE.get(model_id)
    if cached is not None:
        return cached

    with _PIPELINE_LOCK:
        cached = _PIPELINE_CACHE.get(model_id)
        if cached is not None:
            return cached
        from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if device == "cuda" else torch.float32

        tokenizer = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            torch_dtype=dtype,
            device_map="auto" if device == "cuda" else None,
        )
        if device == "cpu":
            model = model.to(device)

        generator = pipeline(
            task="text-generation",
            model=model,
            tokenizer=tokenizer,
            device=0 if device == "cuda" else -1,
        )
        _PIPELINE_CACHE[model_id] = generator
        return generator


class GraniteClient:
    """Talks to IBM Granite locally, on watsonx, or falls back to a stub."""

    def __init__(self, settings_obj=None):
        self.settings = settings_obj or get_settings()

    def explain(self, cognitive_state: dict, prompt_hint: Optional[str] = None) -> dict:
        grounding = self._load_grounding(cognitive_state)

        if self.settings.granite_use_stub:
            return self._stub_explanation(cognitive_state, prompt_hint, grounding)

        if self.settings.granite_use_local:
            try:
                return self._call_local(cognitive_state, prompt_hint, grounding)
            except Exception as exc:
                logger.warning(
                    "Local Granite inference failed (%s). Falling back to watsonx or stub.",
                    exc,
                )

        if self.settings.watsonx_api_key and self.settings.watsonx_project_id:
            try:
                return self._call_watsonx(cognitive_state, prompt_hint, grounding)
            except Exception as exc:
                logger.warning("Granite watsonx call failed, falling back to stub: %s", exc)

        return self._stub_explanation(cognitive_state, prompt_hint, grounding)

    def _load_grounding(self, state: dict) -> List[dict]:
        try:
            from src.backend.knowledge.retriever import top_k_passages

            query_terms = [
                state.get("persona_state", ""),
                state.get("confidence_band", ""),
                "driver stress" if float(state.get("stress_score", 0.0)) > 60.0 else "driver focus",
            ]
            query = " ".join(term for term in query_terms if term)
            passages = top_k_passages(query=query or "driver cognitive state", limit=3)
            return [
                {
                    "document_title": p.document_title,
                    "source_path": p.source_path,
                    "score": round(p.score, 4),
                    "snippet": p.text[:240],
                }
                for p in passages
            ]
        except Exception as exc:
            logger.debug("Grounding retrieval skipped: %s", exc)
            return []

    def _call_local(self, state: dict, prompt_hint: Optional[str], grounding: List[dict]) -> dict:
        model_id = self.settings.granite_model_id
        generator = _load_local_pipeline(model_id)
        prompt = self._build_prompt(state, prompt_hint, grounding)

        outputs = generator(
            prompt,
            max_new_tokens=220,
            do_sample=False,
            num_return_sequences=1,
            pad_token_id=generator.tokenizer.eos_token_id,
        )
        raw = outputs[0].get("generated_text", "") if outputs else ""
        text = raw[len(prompt):].strip() if raw.startswith(prompt) else raw.strip()
        if not text:
            raise RuntimeError("Local Granite returned an empty completion")
        # Trim at the first double newline so a single paragraph is returned.
        text = text.split("\n\n", 1)[0].strip()

        return {
            "text": text,
            "source": "granite-local",
            "model": model_id,
            "tokens": len(generator.tokenizer.encode(text)),
            "grounding": grounding,
        }

    def _call_watsonx(self, state: dict, prompt_hint: Optional[str], grounding: List[dict]) -> dict:
        endpoint = self.settings.watsonx_url.rstrip("/") + "/ml/v1/text/generation?version=2024-05-01"
        prompt = self._build_prompt(state, prompt_hint, grounding)

        payload = {
            "model_id": self.settings.granite_model_id,
            "project_id": self.settings.watsonx_project_id,
            "input": prompt,
            "parameters": {
                "decoding_method": "greedy",
                "max_new_tokens": 220,
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
            "grounding": grounding,
        }

    def _stub_explanation(self, state: dict, prompt_hint: Optional[str], grounding: List[dict]) -> dict:
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
        if grounding:
            narrative += f" Grounded against {len(grounding)} reference passage(s) from the motorsport ontology."
        if prompt_hint:
            narrative += f" Context note: {prompt_hint}."

        return {
            "text": narrative,
            "source": "stub",
            "model": "neuropit-granite-stub",
            "tokens": None,
            "grounding": grounding,
        }

    @staticmethod
    def _build_prompt(state: dict, prompt_hint: Optional[str], grounding: List[dict]) -> str:
        cleaned = {
            "driver_id": state.get("driver_id"),
            "stress_score": state.get("stress_score"),
            "confidence_score": state.get("confidence_score"),
            "fatigue_score": state.get("fatigue_score"),
            "cognitive_load_score": state.get("cognitive_load_score"),
            "attention_stability": state.get("attention_stability"),
            "strategic_reliability": state.get("strategic_reliability"),
            "panic_probability": state.get("panic_probability"),
            "emotional_drift_score": state.get("emotional_drift_score"),
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
        if grounding:
            grounding_block = "\nReference passages:\n" + "\n".join(
                f"- {entry.get('document_title', 'untitled')}: {entry.get('snippet', '')}"
                for entry in grounding
            )
        else:
            grounding_block = ""
        suffix = f"\nContext note: {prompt_hint}" if prompt_hint else ""
        return prefix + body + grounding_block + suffix + "\n\nExplanation:"
