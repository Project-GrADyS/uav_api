"""
Shared fixtures and helpers for integration tests.

Spawns a single SITL-backed API server (session-scoped) shared across all
test files.  Arms and takes off before yielding to tests, then tears down.

Requirements:
    - ArduPilot installed (default ~/ardupilot)
    - xterm available on PATH
    - pytest, requests
"""

import time
import pytest
import requests

from uav_api.run_api import spawn_with_args

BASE_URL = "http://localhost:8001"
SPEEDUP = 5


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def get(path, **kwargs):
    return requests.get(f"{BASE_URL}{path}", timeout=10, **kwargs)


def post(path, json=None, **kwargs):
    return requests.post(f"{BASE_URL}{path}", json=json, timeout=10, **kwargs)


def delete(path, **kwargs):
    return requests.delete(f"{BASE_URL}{path}", timeout=10, **kwargs)


# ── wait helpers ──────────────────────────────────────────────────────────────

def wait_for_api(timeout=90):
    """Poll /telemetry/general until the server is up."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = get("/telemetry/general")
            if r.status_code == 200:
                return
        except requests.ConnectionError:
            pass
        time.sleep(2)
    raise TimeoutError("API did not become ready within timeout")


def wait_for_altitude(target_alt, tolerance=2, timeout=30):
    """Wait until NED altitude (negative-down) stabilises near target."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = get("/telemetry/ned")
        if r.status_code == 200:
            z = r.json()["info"]["position"]["z"]
            if abs(z - (-target_alt)) < tolerance:
                return
        time.sleep(1)
    raise TimeoutError(f"Altitude did not reach {target_alt}m within {timeout}s")


# ── session-scoped fixture: one SITL server for all tests ────────────────────

@pytest.fixture(scope="session", autouse=True)
def api_server():
    """Start the API server with SITL, arm, take off, yield, then tear down."""
    proc = spawn_with_args([
        "--simulated", "true",
        "--ardupilot_path", "~/ardupilot",
        "--speedup", str(SPEEDUP),
        "--port", "8001",
        "--sysid", "1",
    ])

    try:
        wait_for_api(timeout=90)

        # Arm
        r = get("/command/arm")
        assert r.status_code == 200, f"Arm failed: {r.text}"

        # Takeoff
        r = get("/command/takeoff", params={"alt": 15})
        assert r.status_code == 200, f"Takeoff failed: {r.text}"

        # Let the drone reach altitude
        wait_for_altitude(15, tolerance=3, timeout=40)

        yield proc

    finally:
        proc.terminate()
        proc.join(timeout=15)
        if proc.is_alive():
            proc.kill()
            proc.join(timeout=5)
