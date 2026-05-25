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
import socket
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


def _wait_for_influx(timeout: float = 90.0) -> None:
    """Block until InfluxDB accepts a write with the configured token.

    A fresh InfluxDB container takes a few seconds after the port is
    listening before the admin token is fully provisioned. If the
    backend is launched before that point it logs a long burst of
    `401 unauthorized` errors that look alarming. Waiting here keeps
    the log clean.
    """
    import json as _json
    import urllib.error
    import urllib.request

    logger.info("Waiting for InfluxDB to accept authenticated writes...")
    env_lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    env_map = {}
    for line in env_lines:
        if "=" in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition("=")
            env_map[key.strip()] = value.strip()
    token = env_map.get("INFLUXDB_TOKEN") or "neuropit-judge-local-token"
    org = env_map.get("INFLUXDB_ORG") or "neuropit"
    bucket = env_map.get("INFLUXDB_BUCKET") or "neuropit-telemetry"
    url = env_map.get("INFLUXDB_URL") or "http://localhost:8086"

    write_url = f"{url}/api/v2/write?org={org}&bucket={bucket}&precision=s"
    deadline = time.time() + timeout
    last_status = None
    while time.time() < deadline:
        req = urllib.request.Request(
            write_url,
            data=b"bootstrap_probe value=1",
            method="POST",
            headers={"Authorization": f"Token {token}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=2) as resp:
                if 200 <= resp.status < 300:
                    logger.info("InfluxDB ready")
                    return
                last_status = resp.status
        except urllib.error.HTTPError as exc:
            last_status = exc.code
        except Exception as exc:
            last_status = repr(exc)
        time.sleep(2.0)
    logger.warning(
        "InfluxDB did not accept an authenticated write within %.0fs (last status %s); "
        "the backend will log 401 errors until the token is provisioned. "
        "If this persists, run `python scripts/judge_bootstrap.py --reset` once.",
        timeout,
        last_status,
    )


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


def _detect_lan_ip() -> str:
    """Return the laptop's outward facing LAN IPv4 address.

    Used to print a phone friendly URL for the live PPG sensor page.
    Returns 'localhost' if no usable interface can be discovered, in
    which case the judge can still reach the page from the laptop
    itself but the phone path is unavailable.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # The destination does not need to be reachable; this just
            # nudges Windows to pick the interface it would use for
            # outbound traffic, which is usually the active LAN one.
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
        finally:
            sock.close()
        if isinstance(ip, str) and ip:
            return ip
    except Exception:
        pass
    return "localhost"


def _launch_frontend(lan_ip: str) -> Optional[int]:
    frontend_dir = ROOT / "src" / "frontend"
    if not (frontend_dir / "package.json").exists():
        logger.warning("Frontend directory not present, skipping Mission Control launch")
        return None

    # Install npm deps if node_modules is missing. Skip otherwise so a
    # rerun is fast.
    if not (frontend_dir / "node_modules").exists():
        logger.info("Installing frontend dependencies (first time may take a couple of minutes)")
        npm = shutil.which("npm")
        if npm is None:
            logger.warning("`npm` is not on PATH, cannot install frontend deps")
            return None
        install = subprocess.run(
            [npm, "install"], cwd=str(frontend_dir), check=False
        )
        if install.returncode != 0:
            logger.warning("npm install failed with %d", install.returncode)
            return None

    env = os.environ.copy()
    env["NEXT_PUBLIC_NEUROPIT_API_URL"] = f"http://{lan_ip}:8000"

    LOG_DIR.mkdir(exist_ok=True)
    log_path = LOG_DIR / "frontend.log"
    log_handle = open(log_path, "a", encoding="utf-8")
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if npx is None:
        logger.warning("`npx` is not on PATH, cannot launch Mission Control")
        return None
    proc = subprocess.Popen(  # noqa: S603 (judge convenience launcher)
        [npx, "next", "dev", "-H", "0.0.0.0"],
        cwd=str(frontend_dir),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        env=env,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )
    logger.info("Launched frontend (pid %d, log %s)", proc.pid, log_path)
    return proc.pid


def _stop_process(name: str, pid: int) -> None:
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False)
        else:
            os.kill(pid, signal.SIGTERM)
        logger.info("Stopped %s (pid %d)", name, pid)
    except Exception as exc:
        logger.warning("Could not stop %s (pid %d): %s", name, pid, exc)


def up(launch_frontend: bool = True) -> None:
    _check_docker()
    _ensure_env()
    _infra_up()
    _wait_for_kafka()
    _wait_for_influx()
    _bootstrap()

    lan_ip = _detect_lan_ip()

    processes: Dict[str, int] = {
        "backend": _launch("backend", "src.backend.run_backend"),
        "gateway": _launch("gateway", "src.backend.api.gateway"),
        "streamer": _launch("streamer", "src.backend.ingestion.streamer"),
    }
    if launch_frontend:
        frontend_pid = _launch_frontend(lan_ip)
        if frontend_pid is not None:
            processes["frontend"] = frontend_pid
    _record_processes(processes)

    print()
    print("NeuroPit is coming online.")
    print(f"  Mission Control:    http://{lan_ip}:3000")
    print(f"  Live PPG sensor:    http://{lan_ip}:3000/sensor   (open this on your phone)")
    print(f"  Gateway:            http://{lan_ip}:8000/docs")
    print(f"  Redpanda Console:   http://{lan_ip}:8080")
    print()
    print("Phone notes:")
    print("  * Phone must be on the same WiFi as this laptop.")
    print("  * Camera access requires HTTPS on remote IPs in Safari and recent Chrome.")
    print("    On the phone, open chrome://flags/#unsafely-treat-insecure-origin-as-secure")
    print(f"    and whitelist http://{lan_ip}:3000 before opening the sensor page.")
    print()
    print("Backend, gateway, streamer, and frontend logs live in:")
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


def reset_volumes() -> None:
    """Wipe the docker volumes so InfluxDB re-initialises with the
    credentials in the current `.env`. Use when a prior bootstrap left
    InfluxDB seeded with a token that no longer matches.
    """
    logger.warning("Bringing the stack down with -v to wipe persisted volumes")
    _compose(["down", "-v"])
    logger.info("Volumes wiped. Run the bootstrap again without --reset to bring everything back up.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--down", action="store_true", help="Stop the running stack instead of starting it")
    parser.add_argument(
        "--no-frontend",
        action="store_true",
        help="Skip launching Mission Control (judge will run npm run dev manually)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help=(
            "Wipe the docker volumes so InfluxDB re-initialises with the credentials "
            "in the current .env. Use this once if the cognitive engine logs show "
            "'401 unauthorized' against InfluxDB after a fresh bootstrap. Run the "
            "bootstrap again without --reset afterwards."
        ),
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    if args.reset:
        reset_volumes()
        return
    if args.down:
        down()
    else:
        up(launch_frontend=not args.no_frontend)


if __name__ == "__main__":
    main()
