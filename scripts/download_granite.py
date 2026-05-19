"""Download IBM Granite 3.1 8B Instruct to D:\\huggingface only.

Forces every HF cache path (hub, xet, tmp) onto D: so the download cannot
fall back to C:. Run with:

    python scripts/download_granite.py
"""

from __future__ import annotations

import os
import sys

TARGET = r"D:\huggingface"
HUB = TARGET
XET = os.path.join(TARGET, "xet")
TMP = os.path.join(TARGET, "tmp")

for path in (HUB, XET, TMP):
    os.makedirs(path, exist_ok=True)

os.environ["HF_HOME"] = TARGET
os.environ["HF_HUB_CACHE"] = HUB
os.environ["HF_XET_CACHE"] = XET
os.environ["HF_XET_CACHE_DIR"] = XET
os.environ["HUGGINGFACE_HUB_CACHE"] = HUB
os.environ["TMPDIR"] = TMP
os.environ["TEMP"] = TMP
os.environ["TMP"] = TMP

from huggingface_hub import snapshot_download

print(f"target: {TARGET}", flush=True)
print(f"HF_HUB_CACHE={os.environ['HF_HUB_CACHE']}", flush=True)
print(f"TMPDIR={os.environ['TMPDIR']}", flush=True)

path = snapshot_download("ibm-granite/granite-3.1-8b-instruct", cache_dir=HUB)
print(f"DONE -> {path}", flush=True)
