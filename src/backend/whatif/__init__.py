"""Audit log driven What If Replay engine.

The cognitive engine writes a JSONL audit row for every evaluation. Each
row stores the engineered feature vector and the biometric snapshot that
produced the score. That makes the engine deterministically replayable:
plug the same inputs back in and you get the same scores.

This package exposes a small surface for the strategist or analyst to:

- Load a slice of past audit rows for a driver.
- Apply typed mutations to one or more rows (e.g. lower stress, change
  panic events count, alter synthetic heart rate baseline).
- Re run the cognitive engine over the mutated slice.
- Diff the original cognitive trajectory against the mutated one.
- Receive a Granite reasoning paragraph that explains the divergence.

What If is grounded in real session data. It is not a synthetic
counterfactual. The strategist can defend the result because the inputs
are the exact ones the system saw at race time.
"""

from src.backend.whatif.replay import (
    apply_mutations,
    load_audit_window,
    replay_trajectory,
    summarise_trajectory,
)

__all__ = [
    "apply_mutations",
    "load_audit_window",
    "replay_trajectory",
    "summarise_trajectory",
]
