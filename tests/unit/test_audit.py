"""Unit tests for the audit log writer."""

from __future__ import annotations

import json
import os

from src.backend.common import audit
from src.backend.config import get_settings


def test_audit_append_writes_jsonl(tmp_path, monkeypatch):
    monkeypatch.setenv("AUDIT_LOG_DIR", str(tmp_path))
    get_settings.cache_clear()  # type: ignore[attr-defined]

    event = {"kind": "cognitive_evaluation", "driver_id": "VER", "stress": 42.0}
    audit.append(event)

    files = list(tmp_path.glob("cognitive-*.jsonl"))
    assert len(files) == 1
    contents = files[0].read_text(encoding="utf-8").strip().splitlines()
    assert len(contents) == 1
    parsed = json.loads(contents[0])
    assert parsed["kind"] == "cognitive_evaluation"
    assert parsed["driver_id"] == "VER"
    assert parsed["stress"] == 42.0

    get_settings.cache_clear()  # type: ignore[attr-defined]
