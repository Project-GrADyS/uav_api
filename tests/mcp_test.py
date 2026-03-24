"""
Unit tests for the MCP server integration.

Verifies that the FastAPI-MCP server is correctly mounted and all expected
tools are registered with proper operation_ids.

Run:
    pytest tests/mcp_test.py -v
"""

import json
import argparse
import os
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


def make_test_args():
    return argparse.Namespace(
        sysid=1,
        uav_connection="127.0.0.1:17171",
        connection_type="udpin",
        simulated=False,
        gradys_gs=None,
        scripts_path="/tmp/uav_scripts",
        python_path="python3",
        log_console=[],
        log_path=None,
        debug=[],
        script_logs=None,
        port=8000,
    )


@pytest.fixture(scope="module")
def client():
    """Create a TestClient with mocked dependencies, bypassing the lifespan."""
    # Set UAV_ARGS env var so api_app.py module-level code can load
    test_args = make_test_args()
    os.environ["UAV_ARGS"] = json.dumps(vars(test_args))

    # Build a fresh app without the lifespan to avoid SITL/logging setup
    from fastapi import FastAPI
    from uav_api.routers.command import command_router
    from uav_api.routers.movement import movement_router
    from uav_api.routers.telemetry import telemetry_router
    from fastapi_mcp import FastApiMCP

    app = FastAPI(title="UAV API Test")
    app.include_router(command_router)
    app.include_router(movement_router)
    app.include_router(telemetry_router)

    mcp = FastApiMCP(
        app,
        name="UAV MCP Server",
        describe_all_responses=True,
        describe_full_response_schema=True,
    )
    mcp.mount_http(app)

    from uav_api.router_dependencies import get_copter_instance, get_args
    mock_copter = MagicMock()
    app.dependency_overrides[get_copter_instance] = lambda: mock_copter
    app.dependency_overrides[get_args] = lambda: test_args

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    app.dependency_overrides.clear()


def test_mcp_endpoint_exists(client):
    """The /mcp endpoint should be reachable (not 404)."""
    response = client.get("/mcp")
    assert response.status_code != 404


def test_openapi_has_all_operation_ids(client):
    """All endpoints should have explicit operation_ids for MCP tool names."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()

    expected_operation_ids = {
        # Command router
        "arm", "takeoff", "land", "rtl",
        "set_air_speed", "set_ground_speed", "set_climb_speed", "set_descent_speed",
        "set_sim_speedup", "set_home",
        # Movement router
        "go_to_gps", "go_to_gps_wait",
        "go_to_ned", "go_to_ned_wait",
        "drive", "drive_wait",
        "travel_at_ned", "stop", "resume",
        # Telemetry router
        "get_general_telemetry", "get_gps", "get_gps_raw", "get_ned",
        "get_compass", "get_sys_status", "get_sensor_status",
        "get_battery", "get_errors", "get_home",
    }

    actual_operation_ids = set()
    for path_data in schema["paths"].values():
        for method_data in path_data.values():
            if isinstance(method_data, dict) and "operationId" in method_data:
                actual_operation_ids.add(method_data["operationId"])

    missing = expected_operation_ids - actual_operation_ids
    assert not missing, f"Missing operation_ids: {missing}"


def test_no_mission_or_peripherical_routes(client):
    """Mission and peripherical routers should not be registered."""
    response = client.get("/openapi.json")
    schema = response.json()

    all_paths = list(schema["paths"].keys())
    mission_paths = [p for p in all_paths if "/mission" in p]
    peripherical_paths = [p for p in all_paths if "/peripherical" in p]

    assert not mission_paths, f"Mission routes should be removed: {mission_paths}"
    assert not peripherical_paths, f"Peripherical routes should be removed: {peripherical_paths}"


def test_all_endpoints_have_descriptions(client):
    """Every endpoint should have a description for LLM usability."""
    response = client.get("/openapi.json")
    schema = response.json()

    missing_descriptions = []
    for path, path_data in schema["paths"].items():
        for method, method_data in path_data.items():
            if isinstance(method_data, dict) and "operationId" in method_data:
                if not method_data.get("description"):
                    missing_descriptions.append(f"{method.upper()} {path}")

    assert not missing_descriptions, f"Endpoints missing descriptions: {missing_descriptions}"


def test_expected_endpoint_count(client):
    """Should have exactly 29 endpoints (10 command + 9 movement + 10 telemetry)."""
    response = client.get("/openapi.json")
    schema = response.json()

    count = 0
    for path_data in schema["paths"].values():
        for method_data in path_data.values():
            if isinstance(method_data, dict) and "operationId" in method_data:
                count += 1

    assert count == 29, f"Expected 29 endpoints, got {count}"
