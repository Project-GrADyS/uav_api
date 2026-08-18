from fastapi import FastAPI

from uav_api.routers.copter_movement import copter_movement_router
from uav_api.routers.copter_command import copter_command_router
from uav_api.routers.copter_telemetry import copter_telemetry_router
from uav_api.routers.copter_peripherical import copter_peripherical_router
from uav_api.routers.copter_mission import copter_mission_router
from uav_api.routers.plane_command import plane_command_router
from uav_api.routers.plane_movement import plane_movement_router
from uav_api.routers.plane_telemetry import plane_telemetry_router
from uav_api.routers.router_dependencies import get_args
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
        app.include_router(plane_command_router)
        app.include_router(plane_movement_router)
        app.include_router(plane_telemetry_router)
    else:
        app.include_router(copter_command_router)
        app.include_router(copter_telemetry_router)
        app.include_router(copter_movement_router)
        app.include_router(copter_mission_router)
        app.include_router(copter_peripherical_router)
    return app

# uvicorn/hypercorn import this module as "uav_api.api_app:app" after run_api
# has serialized the parsed args into the UAV_ARGS env var. Without UAV_ARGS
# (e.g. in unit tests using create_app directly) no app instance is built.
_env_args = get_args()
if _env_args is not None:
    app = create_app(_env_args)
