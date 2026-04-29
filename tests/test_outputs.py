"""
Functional test verifiers

3 test categories, each checking observable behavior of the running stack:
  1. The Compose stack has Postgres and the NestJS app running, basically 'docker ps'
  2. Both required ports (5432, 8080) are listening.
  3. verify /checkdb
    3.1 GET /checkdb returns HTTP 200.
    3.2 The /checkdb response carries the result of a real SELECT 1 from the DB.
"""

from __future__ import annotations

import re
import socket
import subprocess
import time
from typing import Optional

import pytest
import requests

CHECKDB_HOSTS = ["localhost", "host.docker.internal"]

# How long /checkdb may take to come up after `docker compose up -d`.
CHECKDB_RECOVERY_TIMEOUT_SEC = 35



# Helpers
def _checkdb_url(host: str) -> str:
    return f"http://{host}:8080/checkdb"


def _wait_for_checkdb(timeout: int) -> requests.Response:
    """Poll /checkdb on each candidate host until 200 or timeout."""
    deadline = time.time() + timeout
    last_status: Optional[int] = None
    last_error: Optional[str] = None
    while time.time() < deadline:
        for host in CHECKDB_HOSTS:
            try:
                resp = requests.get(_checkdb_url(host), timeout=3)
                last_status = resp.status_code
                if resp.status_code == 200:
                    return resp
            except requests.RequestException as exc:
                last_error = f"{host}: {exc!r}"
        time.sleep(1)
    pytest.fail(
        f"/checkdb did not return 200 within {timeout}s on any of {CHECKDB_HOSTS}. "
        f"last_status={last_status}, last_error={last_error}"
    )

def _contains_int_one(obj) -> bool:
    """Recursively check whether the integer 1 appears anywhere in the structure."""
    if obj == 1 and isinstance(obj, int) and not isinstance(obj, bool):
        return True
    if isinstance(obj, dict):
        return any(_contains_int_one(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_contains_int_one(v) for v in obj)
    return False


# Test 1 — Compose stack has Postgres and the NestJS app running

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

# Test 2 — Required ports are listening

@pytest.mark.parametrize(
    "port,label",
    [
        (5432, "Postgres"),
        (8080, "NestJS"),
    ],
)
def test_ports_exposed(port: int, label: str) -> None:
    """Required ports must be reachable on at least one of the candidate hosts."""
    last_error = None
    for host in CHECKDB_HOSTS:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(3)
                sock.connect((host, port))
            return  # connected successfully — test passes
        except (ConnectionRefusedError, OSError, socket.timeout) as exc:
            last_error = f"{host}: {exc!r}"
    pytest.fail(
        f"{label} port {port} not listening on any of {CHECKDB_HOSTS}. "
        f"last_error={last_error}"
    )

# Test 3.1 — /checkdb returns 200

def test_checkdb_returns_200() -> None:
    """The probe endpoint must respond with HTTP 200 (with a brief warmup window)."""
    resp = _wait_for_checkdb(timeout=CHECKDB_RECOVERY_TIMEOUT_SEC)
    assert resp.status_code == 200, (
        f"Expected 200, got {resp.status_code}. Body: {resp.text[:300]!r}"
    )

# Test 3.2 — /checkdb actually queries the database

def test_checkdb_actually_queries_db() -> None:
    """The response body must contain the integer 1 (from a real SELECT 1)."""
    resp = _wait_for_checkdb(timeout=CHECKDB_RECOVERY_TIMEOUT_SEC)

    try:
        body = resp.json()
    except ValueError as exc:
        pytest.fail(f"/checkdb response was not JSON: {exc!r} body={resp.text[:300]!r}")

    assert isinstance(body, dict), f"Expected a JSON object, got: {body!r}"
    assert "result" in body, f"Response missing `result` field: {body!r}"

    assert _contains_int_one(body["result"]), (
        f"`result` should contain the integer 1 from SELECT 1, got: {body['result']!r}. "
        "A hardcoded 200 without a real DB query will not pass this check."
    )