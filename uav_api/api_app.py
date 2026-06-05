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

args = get_args()

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

description = f"""
## {args.vehicle.upper()}{" (BETA)"if args.vehicle == "plane" else ""} INFORMATION
* SYSID = **{args.sysid}**
* CONNECTION_STRING = **{args.uav_connection}**
"""

app = FastAPI(
    title="Uav_API",
    summary=f"API designed to simplify vehicle control for Ardupilot UAVs.",
    description=description,
    version="0.2.0",
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