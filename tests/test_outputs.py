"""
Functional verifier for INCUBYTE/hard-devops-task.

3 test categories, each checking observable behavior of the running stack:
  1. The Compose stack has Postgres and the NestJS app running, basically 'docker ps'
  2. Both required ports (5432, 8080) are listening.
  3. verify /checkdb
    3.1 GET /checkdb returns HTTP 200.
    3.2 The /checkdb response carries the result of a real SELECT 1 from the DB.

Tests are intentionally agnostic about how the agent organized their files,
container names, or Compose project name. We assert only on what the user
can observe from the host.
"""

from __future__ import annotations

import subprocess
import re
import socket
import time
from typing import Optional

import pytest
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CHECKDB_URL = "http://localhost:8080/checkdb"

# How long /checkdb may take to come up after `docker compose up -d`.
# Tight enough to discriminate between a properly orchestrated stack
# (typically <20s) and one that race-loops on startup (often 30-60s+).
CHECKDB_RECOVERY_TIMEOUT_SEC = 35


# --- Helpers ---

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


# ---------------------------------------------------------------------------
# Test 1 — Compose stack has Postgres and the NestJS app running - Docker PS
# ---------------------------------------------------------------------------

def test_compose_services_running() -> None:
    """`docker ps` must show running Postgres and app containers."""
    proc = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, f"`docker ps` failed: stderr={proc.stderr}"

    lines = proc.stdout.lower().splitlines()
    has_postgres = any(
        "postgres" in line and ("running" in line or "up" in line)
        for line in lines
    )
    has_app = any(
        re.search(r"(nestjs|nest|node|app|service|api|checkdb)", line)
        and ("running" in line or "up" in line)
        for line in lines
    )

    assert has_postgres, f"Postgres container not running. `docker ps`:\n{proc.stdout}"
    assert has_app, f"App container not running. `docker ps`:\n{proc.stdout}"


# ---------------------------------------------------------------------------
# Test 2 — Assert host ports
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
# Test 3.1 — /checkdb returns 200
# ---------------------------------------------------------------------------

def test_checkdb_returns_200() -> None:
    """The probe endpoint must respond with HTTP 200 (with a brief warmup window)."""
    resp = _wait_for_checkdb(timeout=CHECKDB_RECOVERY_TIMEOUT_SEC)
    assert resp.status_code == 200, (
        f"Expected 200, got {resp.status_code}. Body: {resp.text[:300]!r}"
    )


# ---------------------------------------------------------------------------
# Test 3.2 — /checkdb actually queries the database
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


