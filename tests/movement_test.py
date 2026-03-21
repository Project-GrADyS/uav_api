"""
Integration tests for the movement router.

Spawns a full uav-api server with SITL, arms and takes off,
then exercises every movement endpoint against the live simulation.

Run:
    pytest tests/movement_test.py -v -s --timeout=120
"""

import time
import signal
import pytest
import requests

from uav_api.run_api import run_with_args

BASE_URL = "http://localhost:8001"
SPEEDUP = 5


# ── helpers ──────────────────────────────────────────────────────────────────

def get(path, **kwargs):
    return requests.get(f"{BASE_URL}{path}", timeout=10, **kwargs)


def post(path, json=None, **kwargs):
    return requests.post(f"{BASE_URL}{path}", json=json, timeout=10, **kwargs)


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
            # NED: z is negative when above home
            if abs(z - (-target_alt)) < tolerance:
                return
        time.sleep(1)
    raise TimeoutError(f"Altitude did not reach {target_alt}m within {timeout}s")


# ── session-scoped fixture: one SITL server for all tests ────────────────────

@pytest.fixture(scope="session", autouse=True)
def api_server():
    """Start the API server with SITL, arm, take off, yield, then tear down."""
    proc = run_with_args([
        "--simulated", "true",
        "--ardupilot_path", "~/ardupilot",
        "--speedup", str(SPEEDUP),
        "--port", "8001",
        "--sysid", "1",
    ])

    try:
        # Wait until API + SITL are ready
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
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=15)
        except Exception:
            proc.kill()
            proc.wait(timeout=5)


# ── tests (run in order, share the same SITL session) ────────────────────────

class TestTravelAtNed:
    def test_basic_velocity(self, api_server):
        """POST /movement/travel_at_ned → drone moves north."""
        r = post("/movement/travel_at_ned", json={"x": 2.0, "y": 0.0, "z": 0.0})
        assert r.status_code == 200

        time.sleep(2)

        r = get("/telemetry/ned")
        assert r.status_code == 200
        vx = r.json()["info"]["velocity"]["vx"]
        assert vx > 0.5, f"Expected positive vx, got {vx}"

        r = get("/movement/stop")
        assert r.status_code == 200

    def test_with_look_at_target(self, api_server):
        """POST /movement/travel_at_ned with look_at_target=True."""
        r = post("/movement/travel_at_ned", json={
            "x": 2.0, "y": 0.0, "z": 0.0, "look_at_target": True
        })
        assert r.status_code == 200

        time.sleep(2)

        r = get("/telemetry/ned")
        assert r.status_code == 200
        vx = r.json()["info"]["velocity"]["vx"]
        assert vx > 0.5, f"Expected positive vx, got {vx}"

        r = get("/movement/stop")
        assert r.status_code == 200


class TestGoToNed:
    def test_default_look_at(self, api_server):
        """POST /movement/go_to_ned → drone starts moving toward target."""
        r = post("/movement/go_to_ned", json={"x": 10.0, "y": 0.0, "z": -15.0})
        assert r.status_code == 200

        time.sleep(2)

        r = get("/telemetry/ned")
        assert r.status_code == 200
        pos = r.json()["info"]["position"]
        # Drone should have started moving north (x > 0)
        assert pos["x"] > 0.5, f"Expected drone to move north, x={pos['x']}"

        r = get("/movement/stop")
        assert r.status_code == 200

    def test_with_look_at_target(self, api_server):
        """POST /movement/go_to_ned with look_at_target=True."""
        r = post("/movement/go_to_ned", json={
            "x": 20.0, "y": 0.0, "z": -15.0, "look_at_target": True
        })
        assert r.status_code == 200
        body = r.json()
        assert "result" in body

        r = get("/movement/stop")
        assert r.status_code == 200


class TestDrive:
    def test_drive_with_telemetry(self, api_server):
        """POST /movement/drive → drone moves relative to current position."""
        r = post("/movement/drive", json={"x": 5.0, "y": 0.0, "z": 0.0})
        assert r.status_code == 200

        time.sleep(2)

        r = get("/telemetry/ned")
        assert r.status_code == 200
        vel = r.json()["info"]["velocity"]
        # Should be moving (some non-trivial velocity)
        speed = (vel["vx"] ** 2 + vel["vy"] ** 2) ** 0.5
        assert speed > 0.3, f"Expected movement, speed={speed}"

        r = get("/movement/stop")
        assert r.status_code == 200


class TestGoToGps:
    def test_with_look_at_target(self, api_server):
        """POST /movement/go_to_gps with look_at_target=True."""
        # Get current GPS position
        r = get("/telemetry/gps")
        assert r.status_code == 200
        gps = r.json()["info"]["position"]

        # Offset lat slightly north (~11m per 0.0001 degrees)
        r = post("/movement/go_to_gps/", json={
            "lat": gps["lat"] + 0.0002,
            "long": gps["lon"],
            "alt": gps["relative_alt"],
            "look_at_target": True,
        })
        assert r.status_code == 200

        r = get("/movement/stop")
        assert r.status_code == 200
