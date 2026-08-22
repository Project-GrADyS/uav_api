from importlib.metadata import PackageNotFoundError, version as package_version

from fastapi import FastAPI

from uav_api.routers.copter import command as copter_command, movement as copter_movement, telemetry as copter_telemetry
from uav_api.routers.plane import command as plane_command, movement as plane_movement, telemetry as plane_telemetry
from uav_api.routers.common import mission, peripherical
from uav_api.routers.dependencies import get_args
from uav_api.lifespan import lifespan

metadata = [
{
    "name": "movement",
    "description": "Provides GUIDED movement commands for UAV"
},
{
    "name": "command",
    "description": "Provides general GUIDED commands for UAV"
},
{
    "name": "telemetry",
    "description": "Provides telemetry of the UAV"
},
{
    "name": "mission",
    "description": "Uploads and runs mission scripts on the vehicle's companion computer (each script runs in its own tmux session). Copter mode only."
},
{
    "name": "peripherical",
    "description": "Controls onboard peripherals: camera capture and servo outputs. Copter mode only."
}
]

def _api_version() -> str:
    try:
        return package_version("uav_api")
    except PackageNotFoundError:
        # Running from a source tree without an installed distribution.
        return "0.3.0"

def create_app(args) -> FastAPI:
    description = f"""
Uav_API exposes HTTP endpoints to control an ArduPilot vehicle — real or SITL — over MAVLink.

## {args.vehicle.upper()} INFORMATION
* SYSID = **{args.sysid}** (returned as the `id` field of every response)
* CONNECTION_STRING = **{args.uav_connection}** (connection type: **{args.connection_type}**)
* SIMULATED = **{args.simulated}**
"""

    app = FastAPI(
        title="Uav_API",
        summary="API designed to simplify vehicle control for Ardupilot UAVs.",
        description=description,
        version=_api_version(),
        openapi_tags=metadata,
        lifespan=lifespan
    )
    if args.vehicle == "plane":
        routers = [plane_command.router, plane_movement.router, plane_telemetry.router]
    else:
        routers = [
            copter_command.router,
            copter_telemetry.router,
            copter_movement.router,
            mission.router,
            peripherical.router,
        ]
    for router in routers:
        app.include_router(router)
    return app

# uvicorn/hypercorn import this module as "uav_api.api_app:app" after run_api
# has serialized the parsed args into the UAV_ARGS env var. Without UAV_ARGS
# (e.g. in unit tests using create_app directly) no app instance is built.
_env_args = get_args()
if _env_args is not None:
    app = create_app(_env_args)
