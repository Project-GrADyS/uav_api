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


def _operations(schema):
    for path, methods in schema["paths"].items():
        for method, operation in methods.items():
            yield path, method, operation


def test_every_route_has_a_summary(copter_args, plane_args):
    for args in (copter_args, plane_args):
        schema = create_app(args).openapi()
        missing = [f"{method.upper()} {path}"
                   for path, method, operation in _operations(schema)
                   if not operation.get("summary")]
        assert not missing, f"routes without a summary: {missing}"


def test_every_used_tag_is_described(copter_args, plane_args):
    for args in (copter_args, plane_args):
        schema = create_app(args).openapi()
        described = {tag["name"] for tag in schema.get("tags", []) if tag.get("description")}
        used = {tag for _, _, operation in _operations(schema)
                for tag in operation.get("tags", [])}
        assert used <= described, f"tags without a description: {used - described}"


def test_take_photo_declares_jpeg_response(copter_args):
    schema = create_app(copter_args).openapi()
    responses = schema["paths"]["/peripherical/take_photo"]["get"]["responses"]
    assert "image/jpeg" in responses["200"]["content"]
