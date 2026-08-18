"""
Fixtures for the unit-test layer.

These tests run anywhere — no ArduPilot, no SITL, no MAVLink, no tmux.
Each test gets a FastAPI TestClient built from create_app() with the vehicle
replaced by an autospec mock. The TestClient is deliberately NOT used as a
context manager: entering it would run the lifespan (SITL spawn, MAVLink
connect, scripts watcher), which is exactly what this layer avoids.

The mocks pin the HTTP contract and the router → vehicle delegation, not
MAVLink behavior — the SITL suite in tests/ remains the source of truth
for that.

Telemetry getters must return attribute-bearing objects with numeric fields
in raw MAVLink units (lat in 1e7 degrees, alt in mm, hdg in centidegrees...):
the handlers do the unit conversion arithmetic, which is asserted exactly in
copter_telemetry_unit_test.py.
"""

from unittest.mock import create_autospec

import pytest
from fastapi.testclient import TestClient

from unit_helpers import (
    BATTERY, COMPASS, ERRORS, GENERAL, GPS, HOME, NED, NED_POSITION,
    RAW_GPS, SENSORS, SYS_STATUS,
)

from uav_api.api_app import create_app
from uav_api.args import parse_args
from uav_api.routers.router_dependencies import (
    get_args,
    get_copter_instance,
    get_plane_instance,
    get_scripts_table,
)
from uav_api.vehicles.copter import Copter
from uav_api.vehicles.plane import Plane


def _configure_vehicle_mock(mock):
    mock.armed.return_value = True
    mock.get_general_info.return_value = GENERAL
    mock.get_gps_info.return_value = GPS
    mock.get_home_position.return_value = HOME
    mock.get_battery_info.return_value = BATTERY
    mock.get_sensor_status.return_value = SENSORS
    mock.get_error_info.return_value = ERRORS
    return mock


@pytest.fixture
def copter_args(tmp_path):
    args = parse_args([])
    scripts = tmp_path / "uav_scripts"
    script_logs = tmp_path / "script_logs"
    scripts.mkdir()
    script_logs.mkdir()
    args.scripts_path = str(scripts)
    args.script_logs = str(script_logs)
    return args


@pytest.fixture
def plane_args(tmp_path):
    args = parse_args(["--vehicle", "plane"])
    return args


@pytest.fixture
def fake_copter():
    mock = _configure_vehicle_mock(create_autospec(Copter, instance=True))
    mock.get_raw_gps.return_value = RAW_GPS
    mock.get_ned_info.return_value = NED
    mock.get_ned_position.return_value = NED_POSITION
    mock.get_compass_info.return_value = COMPASS
    mock.get_raw_status_message.return_value = SYS_STATUS
    return mock


@pytest.fixture
def fake_plane():
    return _configure_vehicle_mock(create_autospec(Plane, instance=True))


@pytest.fixture
def scripts_table():
    """Fresh per-test scripts table so mission state can't leak between tests."""
    return {}


@pytest.fixture
def copter_client(copter_args, fake_copter, scripts_table):
    app = create_app(copter_args)
    app.dependency_overrides[get_args] = lambda: copter_args
    app.dependency_overrides[get_copter_instance] = lambda: fake_copter
    app.dependency_overrides[get_scripts_table] = lambda: scripts_table
    return TestClient(app)


@pytest.fixture
def plane_client(plane_args, fake_plane):
    app = create_app(plane_args)
    app.dependency_overrides[get_args] = lambda: plane_args
    app.dependency_overrides[get_plane_instance] = lambda: fake_plane
    return TestClient(app)
