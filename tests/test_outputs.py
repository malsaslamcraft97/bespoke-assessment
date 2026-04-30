from __future__ import annotations

import subprocess
import requests

CHECKDB_HOST = "host.docker.internal"


def _checkdb_url() -> str:
    return f"http://{CHECKDB_HOST}:8080/checkdb"


def _contains_int_one(obj) -> bool:
    if obj == 1 and isinstance(obj, int) and not isinstance(obj, bool):
        return True
    if isinstance(obj, dict):
        return any(_contains_int_one(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_contains_int_one(v) for v in obj)
    return False


def test_compose_services_running() -> None:
    """Both required containers are running and publishing their ports."""
    # Postgres on 5432
    proc = subprocess.run(
        ["docker", "ps", "--filter", "publish=5432", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip(), f"No container publishing port 5432:\n{proc.stdout}"

    # App on 8080
    proc = subprocess.run(
        ["docker", "ps", "--filter", "publish=8080", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip(), f"No container publishing port 8080:\n{proc.stdout}"


def test_exposed_ports():
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}} {{.Ports}}"],
        capture_output=True,
        text=True,
    )
    lines = result.stdout.strip().splitlines()
    port_map = {}
    for line in lines:
        parts = line.split(" ", 1)
        if len(parts) == 2:
            port_map[parts[0]] = parts[1]

    ports_output = result.stdout.strip()
    assert "app-postgres" in ports_output
    assert "5432" in ports_output
    assert "app-nestjs" in ports_output
    assert "8080" in ports_output


def test_checkdb_returns_200() -> None:
    """GET /checkdb returns HTTP 200."""
    resp = requests.get(_checkdb_url())
    assert resp.status_code == 200


def test_checkdb_actually_queries_db() -> None:
    """Response contains the result of a real SELECT 1 query."""
    resp = requests.get(_checkdb_url())
    body = resp.json()
    assert isinstance(body, dict)
    assert "result" in body
    assert _contains_int_one(body["result"])