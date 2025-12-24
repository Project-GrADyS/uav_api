import os
import asyncio

from fastapi import FastAPI
from contextlib import asynccontextmanager
from uav_api.copter_connection import get_copter_instance
from uav_api.routers.movement import movement_router
from uav_api.routers.command import command_router
from uav_api.routers.telemetry import telemetry_router
from uav_api.routers.peripherical import peripherical_router
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
* SYSID = **{args.sysid}**
* CONNECTION_STRING = **{args.uav_connection}**
"""

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Configure loggers
    set_log_config(args)
    # Start SITL
    if args.simulated:
        print("Starting SITL...")
        out_str = f"--out {args.uav_connection} {' '.join([f'--out {address}' for address in args.gs_connection])} "
        home_dir = os.path.expanduser("~")
        ardupilot_logs = os.path.join(home_dir, "uav_api_logs", "ardupilot_logs")
        sitl_command = f"xterm -e {args.ardupilot_path}/Tools/autotest/sim_vehicle.py -v ArduCopter -I {args.sysid} --sysid {args.sysid} -N -L {args.location} --speedup {args.speedup} {out_str} --use-dir={ardupilot_logs} &"
        os.system(sitl_command)
        print("SITL started.")
    copter = get_copter_instance(args.sysid, args.uav_connection if args.connection_type == "usb" else f"{args.connection_type}:{args.uav_connection}")
    
    # Starting task that will continuously drain MAVLink messages
    print("Starting Drain MAVLink loop...")
    drain_mav_loop = asyncio.create_task(copter.run_drain_mav_loop())

    # If defined, start location thread for Gradys Ground Station
    if args.gradys_gs is not None:
        print("Starting Gradys GS location task...")
        location_coroutine = asyncio.create_task(copter.send_location_to_gradys_gs(args.sysid, args.port, args.gradys_gs))
    
    print("API is ready.")
    yield
    print("Shutting down API...")

    # Close SITL
    if args.simulated:
        print("Closing SITL...")
        os.system("pkill xterm")
        print("SITL closed.")

    # Cancelling Drain Mav Loop Task
    print("Cancelling Drain MAVLink loop...")
    drain_mav_loop.cancel()

    try:
        await drain_mav_loop
    except asyncio.CancelledError:
        print("Drain MAVLink loop has been cancelled.")

    # Cancelling location coroutine if it was started
    if args.gradys_gs is not None:
        print("Cancelling Gradys GS location task...")
        location_coroutine.cancel()

        try:
            await location_task
        except asyncio.CancelledError:
            print("Location task has been cancelled.")
app = FastAPI(
    title="Uav_API",
    summary=f"API designed to simplify Copter control for Ardupilot UAVs (for now only QuadCopter is supported).",
    description=description,
    version="0.0.4",
    openapi_tags=metadata,
    lifespan=lifespan
)
app.include_router(movement_router)
app.include_router(command_router)
app.include_router(telemetry_router)
app.include_router(peripherical_router)
