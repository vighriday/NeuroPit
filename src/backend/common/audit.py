"""Audit log writer.

Every cognitive decision is appended to a JSON Lines file on disk. The file
captures the inputs, the active weights, the cognitive scores, and the
confidence band, so any past decision can be inspected later without
replaying the entire stream. Race day operators need this. Investigators
need this. The dashboard does not read from it directly.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import date
from typing import Any, Dict

from src.backend.config import get_settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()


def _resolve_log_path() -> str:
    settings = get_settings()
    log_dir = settings.audit_log_dir
    os.makedirs(log_dir, exist_ok=True)
    filename = f"cognitive-{date.today().isoformat()}.jsonl"
    return os.path.join(log_dir, filename)


def append(event: Dict[str, Any]) -> None:
    """Append a single event to today's audit log file.

    Raises on disk failure so the caller can decide whether to drop the
    matching broadcast. The function is safe to call from multiple
    threads in a single process. Cross process safety is intentionally
    not promised. Each worker uses its own writer.
    """
    path = _resolve_log_path()
    payload = json.dumps(event, default=str) + "\n"
    with _lock:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(payload)


def try_append(event: Dict[str, Any]) -> bool:
    """Best effort append. Returns True on success.

    Use this when the producer is not load bearing for trust guarantees,
    for example background telemetry. The cognitive engine, the
    prescription worker, and the what if replay route call ``append``
    instead and skip their broadcast when it raises.
    """
    try:
        append(event)
        return True
    except Exception as exc:
        logger.warning("Audit log write failed: %s", exc)
        return False
