"""
Functional verifier for INCUBYTE/hard-devops-task.

Six tests, each checking observable behavior of the running stack:
  1. Docker Engine + Compose plugin are installed and reachable.
  2. The Compose stack has Postgres and the NestJS app running.
  3. Both required ports (5432, 8080) are listening.
  4. GET /checkdb returns HTTP 200.
  5. The /checkdb response carries the result of a real SELECT 1 from the DB.
  6. The endpoint stays reachable across multiple cold-restart cycles.

Tests are intentionally agnostic about how the agent organized their files,
container names, or Compose project name. We assert only on what the user
can observe from the host.
"""

from __future__ import annotations

import re
import socket
import subprocess
import time
from pathlib import Path
from typing import Optional

import pytest
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CHECKDB_URL = "http://localhost:8080/checkdb"
APP_DIR = Path("/app")

# How long /checkdb may take to come up after `docker compose up -d`.
# Tight enough to discriminate between a properly orchestrated stack
# (typically <20s) and one that race-loops on startup (often 30-60s+).
CHECKDB_RECOVERY_TIMEOUT_SEC = 35

# How many cold-restart cycles to perform in the resilience test.
RESTART_CYCLES = 3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(
    cmd: list[str],
    timeout: int = 30,
    cwd: Optional[Path] = None,
) -> tuple[int, str, str]:
    """Run a subprocess and return (returncode, stdout, stderr)."""
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(cwd) if cwd else None,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _find_compose_file() -> Path:
    """Locate the agent's compose file under /app/.

    Accepts any of the four canonical filenames at /app/ itself or in any
    immediate subdirectory of /app/ (e.g. /app/compose/docker-compose.yml).
    Deeper paths and node_modules are excluded to avoid false positives.
    """
    filenames = [
        "docker-compose.yml",
        "docker-compose.yaml",
        "compose.yml",
        "compose.yaml",
    ]
    candidates: list[Path] = []
    for name in filenames:
        candidates.extend(APP_DIR.glob(name))
        candidates.extend(APP_DIR.glob(f"*/{name}"))
    # Filter out anything that slipped in from build artifacts
    candidates = [c for c in candidates if "node_modules" not in c.parts]
    if candidates:
        return candidates[0]
    pytest.fail(
        f"No compose file found at /app/ or one level deep. "
        f"Looked for {filenames} under /app/ and /app/*/."
    )


def _wait_for_checkdb(timeout: int) -> requests.Response:
    """Poll /checkdb until 200 or timeout. Returns the successful response."""
    deadline = time.time() + timeout
    last_status: Optional[int] = None
    last_error: Optional[str] = None
    while time.time() < deadline:
        try:
            resp = requests.get(CHECKDB_URL, timeout=3)
            last_status = resp.status_code
            if resp.status_code == 200:
                return resp
        except requests.RequestException as exc:
            last_error = repr(exc)
        time.sleep(1)
    pytest.fail(
        f"/checkdb did not return 200 within {timeout}s. "
        f"last_status={last_status}, last_error={last_error}"
    )


def _compose(args: list[str], compose_file: Path, timeout: int = 60) -> tuple[int, str, str]:
    """Invoke `docker compose -f <file> ...` from /app/."""
    return _run(
        ["docker", "compose", "-f", str(compose_file), *args],
        timeout=timeout,
        cwd=APP_DIR,
    )


# ---------------------------------------------------------------------------
# Test 1 — Docker is installed and the daemon is reachable
# ---------------------------------------------------------------------------

def test_docker_installed_via_ansible() -> None:
    """Docker Engine and the Compose plugin must be installed and runnable."""
    rc, out, err = _run(["docker", "--version"])
    assert rc == 0, f"`docker --version` failed: rc={rc} stderr={err}"
    assert "Docker version" in out, f"Unexpected `docker --version` output: {out!r}"

    rc, out, err = _run(["docker", "compose", "version"])
    assert rc == 0, f"`docker compose version` failed: rc={rc} stderr={err}"
    assert "Docker Compose" in out or "compose version" in out.lower(), (
        f"Unexpected `docker compose version` output: {out!r}"
    )

    # The daemon itself must be reachable, not merely the CLI installed.
    rc, out, err = _run(["docker", "info"])
    assert rc == 0, f"`docker info` failed; daemon may not be running. stderr={err}"
    assert "Server Version" in out, "`docker info` did not report a Server Version"


# ---------------------------------------------------------------------------
# Test 2 — Compose stack has Postgres and the NestJS app running
# ---------------------------------------------------------------------------

def test_compose_services_running() -> None:
    """`docker compose ps` must show a running Postgres and a running app service."""
    compose_file = _find_compose_file()
    rc, out, err = _compose(["ps"], compose_file)
    assert rc == 0, f"`docker compose ps` failed: stderr={err}"

    lines = out.lower().splitlines()
    has_postgres = any(
        "postgres" in line and ("running" in line or "up" in line)
        for line in lines
    )
    has_app = any(
        re.search(r"(nestjs|nest|node|app|service|api|checkdb)", line)
        and ("running" in line or "up" in line)
        for line in lines
    )

    assert has_postgres, f"Postgres service not running. `docker compose ps`:\n{out}"
    assert has_app, f"App service not running. `docker compose ps`:\n{out}"


# ---------------------------------------------------------------------------
# Test 3 — Required host ports are listening
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "port,label",
    [
        (5432, "Postgres"),
        (8080, "NestJS"),
    ],
)
def test_ports_exposed(port: int, label: str) -> None:
    """Both required ports must be reachable on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(3)
        try:
            sock.connect(("127.0.0.1", port))
        except (ConnectionRefusedError, OSError, socket.timeout) as exc:
            pytest.fail(f"{label} port {port} not listening: {exc!r}")


# ---------------------------------------------------------------------------
# Test 4 — /checkdb returns 200
# ---------------------------------------------------------------------------

def test_checkdb_returns_200() -> None:
    """The probe endpoint must respond with HTTP 200 (with a brief warmup window)."""
    resp = _wait_for_checkdb(timeout=CHECKDB_RECOVERY_TIMEOUT_SEC)
    assert resp.status_code == 200, (
        f"Expected 200, got {resp.status_code}. Body: {resp.text[:300]!r}"
    )


# ---------------------------------------------------------------------------
# Test 5 — /checkdb actually queries the database
# ---------------------------------------------------------------------------

def test_checkdb_actually_queries_db() -> None:
    """The response body must contain the integer 1 (from a real SELECT 1)."""
    resp = _wait_for_checkdb(timeout=CHECKDB_RECOVERY_TIMEOUT_SEC)

    try:
        body = resp.json()
    except ValueError as exc:
        pytest.fail(f"/checkdb response was not JSON: {exc!r} body={resp.text[:300]!r}")

    assert isinstance(body, dict), f"Expected a JSON object, got: {body!r}"
    assert "result" in body, f"Response missing `result` field: {body!r}"
    assert body["result"] == 1, (
        f"`result` should equal 1 from SELECT 1, got: {body['result']!r}. "
        "A hardcoded 200 without a real DB query will not pass this check."
    )


# ---------------------------------------------------------------------------
# Test 6 — Resilience across cold-restart cycles
# ---------------------------------------------------------------------------

def test_resilient_to_restart_cycles() -> None:
    """The stack must produce a working /checkdb after multiple `down -v && up -d` cycles.

    A naive `depends_on` (without a healthcheck on Postgres and a `service_healthy`
    condition on the dependent service) often passes a single cold start by luck,
    then races on subsequent ones because the NestJS container starts before
    Postgres is ready to accept connections.
    """
    compose_file = _find_compose_file()

    for cycle in range(1, RESTART_CYCLES + 1):
        rc, _, err = _compose(["down", "-v"], compose_file, timeout=120)
        assert rc == 0, f"cycle {cycle}: `docker compose down -v` failed: {err}"

        rc, _, err = _compose(["up", "-d"], compose_file, timeout=180)
        assert rc == 0, f"cycle {cycle}: `docker compose up -d` failed: {err}"

        try:
            resp = _wait_for_checkdb(timeout=CHECKDB_RECOVERY_TIMEOUT_SEC)
        except Exception as exc:  # noqa: BLE001
            pytest.fail(
                f"cycle {cycle}: /checkdb did not recover within "
                f"{CHECKDB_RECOVERY_TIMEOUT_SEC}s after `up -d`: {exc!r}"
            )

        body = resp.json()
        assert body.get("result") == 1, (
            f"cycle {cycle}: /checkdb came up but result != 1 (body={body!r})"
        )