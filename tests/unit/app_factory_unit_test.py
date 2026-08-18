"""Unit tests for create_app: vehicle-dependent router registration and a
clean OpenAPI schema for both variants."""

from uav_api.api_app import create_app


def openapi_paths(args):
    # include_router is lazy in recent FastAPI (routes materialize at app
    # setup), so the OpenAPI schema is the reliable view of what's registered.
    return set(create_app(args).openapi()["paths"])


def test_copter_app_registers_copter_routers(copter_args):
    paths = openapi_paths(copter_args)
    assert "/mission/execute-script/" in paths
    assert "/mission/running-scripts" in paths
    assert "/movement/go_to_ned" in paths
    assert "/peripherical/take_photo" in paths
    # plane-only endpoints must be absent
    assert "/command/disarm" not in paths
    assert "/movement/stop" not in paths


def test_plane_app_registers_plane_routers(plane_args):
    paths = openapi_paths(plane_args)
    assert "/command/arm" in paths
    assert "/command/land_at" in paths
    assert "/movement/stop" in paths
    assert "/telemetry/general" in paths
    # copter-only routers must be absent
    assert not any(path.startswith("/mission") for path in paths)
    assert not any(path.startswith("/peripherical") for path in paths)
    assert "/movement/go_to_ned" not in paths


def test_openapi_serves_for_both_vehicles(copter_client, plane_client):
    assert copter_client.get("/openapi.json").status_code == 200
    assert plane_client.get("/openapi.json").status_code == 200


def test_vehicle_dependency_adds_no_query_params(copter_client):
    """The old constructor-as-dependency leaked phantom sysid/connection query
    params into every endpoint's schema; the init/get split removes them."""
    schema = copter_client.get("/openapi.json").json()
    arm = schema["paths"]["/command/arm"]["get"]
    param_names = {p["name"] for p in arm.get("parameters", [])}
    assert "sysid" not in param_names
    assert "connection" not in param_names
