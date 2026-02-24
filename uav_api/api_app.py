import os
import asyncio
import aiohttp
import signal
import psutil
import subprocess

from fastapi import FastAPI
from contextlib import asynccontextmanager
from uav_api.router_dependencies import get_copter_instance
from uav_api.routers.movement import movement_router
from uav_api.routers.command import command_router
from uav_api.routers.telemetry import telemetry_router
from uav_api.routers.peripherical import peripherical_router
from uav_api.routers.mission import mission_router
from uav_api.log import set_log_config
from uav_api.args import read_args_from_env
from uav_api.gradys_gs import send_location_to_gradys_gs

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

def kill_sitl_by_tag(tag_value):
    """
    Scans ALL system processes and kills those with the matching environment tag.
    """
    for proc in psutil.process_iter(['environ', 'name', 'pid']):
        try:
            # Check if our custom variable is in the process environment
            env = proc.info.get('environ')
            if env and env.get("UAV_SITL_TAG") == tag_value:
                print(f"Found rogue process: {proc.info['name']} (PID: {proc.info['pid']}). Killing...")
                proc.kill() # Use kill() for xterms as they can be stubborn
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Configure loggers
    set_log_config(args)
    # Start SITL
    if args.simulated:
        print("Starting SITL...")
    # Create a unique tag for this specific SITL instance
        sitl_tag = f"SITL_ID_{args.sysid}"
    
        # Add the tag to the environment variables
        env = os.environ.copy()
        env["UAV_SITL_TAG"] = sitl_tag 

        # Expand the path as discussed before
        ardupilot_base = os.path.expanduser(args.ardupilot_path)
        script_path = os.path.join(ardupilot_base, "Tools/autotest/sim_vehicle.py")
        
        out_str = f"--out {args.uav_connection} {' '.join([f'--out {address}' for address in args.gs_connection])} "
        home_dir = os.path.expanduser("~")
        ardupilot_logs = os.path.join(home_dir, "uav_api_logs", "ardupilot_logs")
        sitl_command = f"xterm -e {script_path} -v ArduCopter -I {args.sysid} --sysid {args.sysid} -N -L {args.location} --speedup {args.speedup} {out_str} --use-dir={ardupilot_logs}"
        
        # Start the process with the custom environment
        sitl_process = subprocess.Popen(sitl_command.split(" "), env=env)
        print(f"SITL started with PID {sitl_process.pid}.")
    copter = get_copter_instance(args.sysid, args.uav_connection if args.connection_type == "usb" else f"{args.connection_type}:{args.uav_connection}")
    
    # Starting task that will continuously drain MAVLink messages
    print("Starting Drain MAVLink loop...")
    drain_mav_loop = asyncio.create_task(copter.run_drain_mav_loop())

    # If defined, start location thread for Gradys Ground Station
    if args.gradys_gs is not None:
        print("Starting Gradys GS location task...")
        session = aiohttp.ClientSession()
        location_task = asyncio.create_task(send_location_to_gradys_gs(copter, session, args.port, args.gradys_gs))
    
    print("API is ready.")
    yield
    print("Shutting down API...")

    # Close SITL
    if args.simulated:
        print("Closing SITL and all associated windows...")
        kill_sitl_by_tag(sitl_tag)
        print("SITL and associated windows closed.")

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
        location_task.cancel()

        try:
            await location_task
        except asyncio.CancelledError:
            print("Location task has been cancelled.")

        await session.close()
        print("Gradys GS location task closed.")
app = FastAPI(
    title="Uav_API",
    summary=f"API designed to simplify Copter control for Ardupilot UAVs (for now only QuadCopter is supported).",
    description=description,
    version="0.0.4",
    openapi_tags=metadata,
    lifespan=lifespan
)
app.include_router(command_router)
app.include_router(telemetry_router)
app.include_router(movement_router)
app.include_router(mission_router)
app.include_router(peripherical_router)