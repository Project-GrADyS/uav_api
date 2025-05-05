import os

from fastapi import FastAPI
from contextlib import asynccontextmanager
from uav_api.copter_connection import get_copter_instance
from uav_api.routers.movement import movement_router
from uav_api.routers.command import command_router
from uav_api.routers.telemetry import telemetry_router
from uav_api.log import set_log_config
from uav_api.args import read_args_from_env

args = read_args_from_env()

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
## COPTER INFORMATION
* SYSID = **{10}**
* CONNECTION_STRING = **{'aaa'}**
"""

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Configure loggers
    set_log_config(args)
    # Start SITL
    if args.simulated:
        out_str = f"--out {args.uav_connection} {' '.join([f'--out {address}' for address in args.gs_connection])} "
        home_dir = os.path.expanduser("~")
        ardupilot_logs = os.path.join(home_dir, "uav_api_logs", "ardupilot_logs")
        sitl_command = f"xterm -e {args.ardupilot_path}/Tools/autotest/sim_vehicle.py -v ArduCopter -I {args.sysid} --sysid {args.sysid} -N -L {args.location} --speedup {args.speedup} {out_str} --use-dir={ardupilot_logs} &"
        os.system(sitl_command)
    get_copter_instance(args.sysid, f"{args.connection_type}:{args.uav_connection}")
    yield
    # Close SITL
    if args.simulated:
        os.system("pkill xterm")

app = FastAPI(
    title="UavControl API",
    summary=f"API designed to simplify Copter control with Ardupilot",
    description=description,
    version="0.0.1",
    contact={
        "name": "Francisco Fleury",
        "email": "franmeifleury@gmail.com",
    },
    openapi_tags=metadata,
    lifespan=lifespan
)
app.include_router(movement_router)
app.include_router(command_router)
app.include_router(telemetry_router)