"""One command judge bootstrap.

This script exists so a judge can clone the repository and bring the
full NeuroPit stack online with a single Python invocation, regardless
of operating system. It performs the work that the Makefile targets
do, but it does not depend on `make` being on the PATH, which is the
single most common reason a Windows clone fails to boot for a judge.

Behaviour
---------

1. Verifies Docker is reachable. Exits with a helpful message if not.
2. Copies `.env.example` to `.env` if `.env` is missing, and replaces
   the two `replace-with-...` placeholders with deterministic local
   defaults so the compose stack actually starts. The judge can swap
   these later for real values; the defaults are fine for evaluation.
3. Brings up the docker compose stack (Redpanda, InfluxDB, Qdrant,
   Redpanda Console).
4. Runs `init_infrastructure` to create Kafka topics and Qdrant
   collections.
5. Launches the backend worker pool, the FastAPI gateway, and the
   FastF1 streamer as background subprocesses, with their stdout
   redirected into log files under `logs/`.
6. Prints the URLs the judge should open.

The script is intentionally idempotent. Running it twice is safe.
A `--down` flag stops the stack and removes the launched processes.

Cross platform notes
--------------------
The subprocess calls use `python -m <module>` so the same command
works on Windows and Unix. We avoid shell features. Process handles
are written to `logs/processes.json` so a separate invocation can
shut them down even after the original terminal closes.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("judge_bootstrap")

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
ENV_EXAMPLE_PATH = ROOT / ".env.example"
COMPOSE_PATH = ROOT / "infrastructure" / "docker-compose.yml"
LOG_DIR = ROOT / "logs"
PROCESS_RECORD = LOG_DIR / "processes.json"

PYTHON = sys.executable

_DEFAULT_REPLACEMENTS = {
    "replace-with-a-long-random-token": "neuropit-judge-local-token",
    "replace-with-a-strong-local-password": "neuropit-judge-local-password",
}


def _run(args, **kwargs) -> subprocess.CompletedProcess:
    logger.info("Running: %s", " ".join(str(a) for a in args))
    return subprocess.run(args, cwd=str(ROOT), check=False, **kwargs)


def _check_docker() -> None:
    if shutil.which("docker") is None:
        logger.error("`docker` is not on PATH. Install Docker Desktop and re run this script.")
        sys.exit(2)
    probe = _run(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if probe.returncode != 0:
        logger.error(
            "Docker daemon is not reachable. Start Docker Desktop and wait for the whale icon to settle, then re run this script."
        )
        sys.exit(2)


def _ensure_env() -> None:
    if ENV_PATH.exists():
        text = ENV_PATH.read_text(encoding="utf-8")
        changed = False
        for placeholder, value in _DEFAULT_REPLACEMENTS.items():
            if placeholder in text:
                text = text.replace(placeholder, value)
                changed = True
        if changed:
            ENV_PATH.write_text(text, encoding="utf-8")
            logger.info("Replaced placeholder values in existing .env so the stack can start")
        return

    if not ENV_EXAMPLE_PATH.exists():
        logger.error(".env.example is missing. Cannot bootstrap.")
        sys.exit(2)

    text = ENV_EXAMPLE_PATH.read_text(encoding="utf-8")
    for placeholder, value in _DEFAULT_REPLACEMENTS.items():
        text = text.replace(placeholder, value)
    ENV_PATH.write_text(text, encoding="utf-8")
    logger.info("Wrote .env from .env.example with judge defaults filled in")


def _compose(args: List[str], capture: bool = False) -> subprocess.CompletedProcess:
    return _run(
        ["docker", "compose", "--env-file", str(ENV_PATH), "-f", str(COMPOSE_PATH), *args],
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
        text=True,
    )


def _infra_up() -> None:
    res = _compose(["up", "-d"])
    if res.returncode != 0:
        logger.error("Docker compose failed to bring the infra up")
        sys.exit(2)


def _wait_for_kafka(timeout: float = 60.0) -> None:
    logger.info("Waiting for Redpanda to accept connections...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        probe = _run(
            ["docker", "exec", "neuropit-redpanda", "rpk", "cluster", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if probe.returncode == 0:
            logger.info("Redpanda ready")
            return
        time.sleep(2.0)
    logger.warning("Redpanda did not become ready within %.0fs, attempting bootstrap anyway", timeout)


def _bootstrap() -> None:
    res = _run([PYTHON, "-m", "src.backend.init_infrastructure"])
    if res.returncode != 0:
        logger.error("init_infrastructure exited with %d", res.returncode)
        sys.exit(2)


def _launch(name: str, module: str) -> int:
    LOG_DIR.mkdir(exist_ok=True)
    log_path = LOG_DIR / f"{name}.log"
    log_handle = open(log_path, "a", encoding="utf-8")
    proc = subprocess.Popen(  # noqa: S603 (judge convenience launcher)
        [PYTHON, "-m", module],
        cwd=str(ROOT),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )
    logger.info("Launched %s (pid %d, log %s)", name, proc.pid, log_path)
    return proc.pid


def _record_processes(processes: Dict[str, int]) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    PROCESS_RECORD.write_text(json.dumps(processes, indent=2), encoding="utf-8")


def _read_process_record() -> Dict[str, int]:
    if not PROCESS_RECORD.exists():
        return {}
    try:
        return json.loads(PROCESS_RECORD.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _stop_process(name: str, pid: int) -> None:
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False)
        else:
            os.kill(pid, signal.SIGTERM)
        logger.info("Stopped %s (pid %d)", name, pid)
    except Exception as exc:
        logger.warning("Could not stop %s (pid %d): %s", name, pid, exc)


def up() -> None:
    _check_docker()
    _ensure_env()
    _infra_up()
    _wait_for_kafka()
    _bootstrap()

    processes: Dict[str, int] = {
        "backend": _launch("backend", "src.backend.run_backend"),
        "gateway": _launch("gateway", "src.backend.api.gateway"),
        "streamer": _launch("streamer", "src.backend.ingestion.streamer"),
    }
    _record_processes(processes)

    print()
    print("NeuroPit is coming online.")
    print("  Mission Control:    http://localhost:3000  (run `npm run dev` inside src/frontend)")
    print("  Gateway:            http://localhost:8000/docs")
    print("  Live PPG sensor:    http://localhost:3000/sensor")
    print("  Redpanda Console:   http://localhost:8080")
    print()
    print("Backend, gateway, and streamer logs live in:")
    print(f"  {LOG_DIR}")
    print()
    print("To shut everything down: python scripts/judge_bootstrap.py --down")


def down() -> None:
    processes = _read_process_record()
    for name, pid in processes.items():
        _stop_process(name, pid)
    if PROCESS_RECORD.exists():
        PROCESS_RECORD.unlink()
    _compose(["down"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--down", action="store_true", help="Stop the running stack instead of starting it")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    if args.down:
        down()
    else:
        up()


if __name__ == "__main__":
    main()
