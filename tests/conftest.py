"""Pytest configuration shared by every NeuroPit test.

Ensures the repository root is on `sys.path` so tests can import the backend
package using the same dotted path the runtime code uses, namely
`src.backend.something`.
"""

from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
