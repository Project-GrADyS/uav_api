"""
Integration tests for the command router (uav_api/routers/command.py).

A real ArduPilot SITL instance is started once for the session. All flight
sequence tests share a single Copter connected to it and run in definition
order (ground → arm → takeoff → land).

Prerequisites:
  - ArduPilot installed at ~/ardupilot
  - Location "AbraDF" registered in ~/.config/ardupilot/locations.txt

Run all tests (requires ArduPilot):
    pytest tests/command_test.py -v -s

Run only parameter validation tests (no SITL required):
    pytest tests/command_test.py -v -k "missing_param"
"""

import argparse
import os
import subprocess
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from uav_api.copter import Copter
from uav_api.router_dependencies import get_args, get_copter_instance
from uav_api.routers.command import command_router

ARDUPILOT_PATH = os.path.expanduser("~/ardupilot")
SITL_SCRIPT = os.path.join(ARDUPILOT_PATH, "Tools/autotest/sim_vehicle.py")
SITL_OUT = "127.0.0.1:17171"
SITL_CONNECTION = "udpin:127.0.0.1:17171"


# ---------------------------------------------------------------------------
# Session-scoped SITL fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def sitl():
    proc = subprocess.Popen(
        [
            "python3", SITL_SCRIPT,
            "-v", "ArduCopter",
            "-I", "1", "--sysid", "1",
            "-N",               # skip rebuild
            "--no-mavproxy",    # prevents mavproxy (and its xterm) from spawning
            "-L", "AbraDF",
            "--speedup", "10",
            "--out", SITL_OUT,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    yield proc
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture(scope="session")
def copter(sitl):
    c = Copter(sysid=1)
    c.connect(SITL_CONNECTION)
    c.wait_heartbeat(timeout=60)
    return c


@pytest.fixture(scope="session")
def client(copter):
    app = FastAPI()
    app.include_router(command_router)
    app.dependency_overrides[get_copter_instance] = lambda: copter
    app.dependency_overrides[get_args] = lambda: argparse.Namespace(sysid=1)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Lightweight mock fixture (no SITL needed)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_client():
    app = FastAPI()
    app.include_router(command_router)
    app.dependency_overrides[get_copter_instance] = lambda: MagicMock()
    app.dependency_overrides[get_args] = lambda: argparse.Namespace(sysid=1)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def assert_ok(r, expected_result=None):
    assert r.status_code == 200
    body = r.json()
    assert body["device"] == "uav"
    assert body["id"] == "1"
    if expected_result is not None:
        assert body["result"] == expected_result
    return body


# ---------------------------------------------------------------------------
# Flight sequence tests (order matters — runs in definition order)
# ---------------------------------------------------------------------------

class TestFlightSequence:
    def test_set_home(self, client):
        r = client.get("/command/set_home")
        assert_ok(r, "Home location set successfully!")

    def test_set_sim_speedup(self, client):
        r = client.get("/command/set_sim_speedup?sim_factor=10")
        assert_ok(r, "Simulation speedup set to 10.0x")

    def test_set_air_speed(self, client):
        r = client.get("/command/set_air_speed?new_v=5")
        assert_ok(r, "Air speed set to 5m/s")

    def test_set_ground_speed(self, client):
        r = client.get("/command/set_ground_speed?new_v=5")
        assert_ok(r, "Ground speed set to 5m/s")

    def test_set_climb_speed(self, client):
        r = client.get("/command/set_climb_speed?new_v=3")
        assert_ok(r, "Climb speed set to 3m/s")

    def test_set_descent_speed(self, client):
        r = client.get("/command/set_descent_speed?new_v=3")
        assert_ok(r, "Descent speed set to 3m/s")

    def test_arm(self, client):
        r = client.get("/command/arm")
        assert_ok(r, "Armed vehicle")

    def test_takeoff(self, client):
        r = client.get("/command/takeoff?alt=10")
        assert_ok(r, "Takeoff successful! Vehicle at 10 meters")

    def test_land(self, client):
        r = client.get("/command/land")
        assert_ok(r, "Landed at home successfully")


# ---------------------------------------------------------------------------
# Parameter validation tests (no SITL required)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", [
    "/command/set_air_speed",
    "/command/set_ground_speed",
    "/command/set_climb_speed",
    "/command/set_descent_speed",
    "/command/set_sim_speedup",
])
def test_missing_param_returns_422(mock_client, path):
    r = mock_client.get(path)
    assert r.status_code == 422
