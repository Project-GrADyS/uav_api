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
}
]

def create_app(args) -> FastAPI:
    description = f"""
## {args.vehicle.upper()} INFORMATION
* SYSID = **{args.sysid}**
* CONNECTION_STRING = **{args.uav_connection}**
"""

    app = FastAPI(
        title="Uav_API",
        summary="API designed to simplify vehicle control for Ardupilot UAVs.",
        description=description,
        version="0.2.2",
        openapi_tags=metadata,
        lifespan=lifespan
    )
    if args.vehicle == "plane":
        app.include_router(plane_command.router)
        app.include_router(plane_movement.router)
        app.include_router(plane_telemetry.router)
    else:
        app.include_router(copter_command.router)
        app.include_router(copter_telemetry.router)
        app.include_router(copter_movement.router)
        app.include_router(mission.router)
        app.include_router(peripherical.router)
    return app

# uvicorn/hypercorn import this module as "uav_api.api_app:app" after run_api
# has serialized the parsed args into the UAV_ARGS env var. Without UAV_ARGS
# (e.g. in unit tests using create_app directly) no app instance is built.
_env_args = get_args()
if _env_args is not None:
    app = create_app(_env_args)
