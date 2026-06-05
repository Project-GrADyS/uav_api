import os
import asyncio
import logging
import aiohttp
import psutil
import subprocess

from datetime import datetime
from fastapi import FastAPI
from contextlib import asynccontextmanager
from uav_api.routers.router_dependencies import get_args, get_copter_instance, get_plane_instance, get_scripts_table
from uav_api.gradys_gs import send_location_to_gradys_gs
from uav_api.log import set_log_config

logger = logging.getLogger("SYSTEM")

args = get_args()

async def scripts_watcher_loop(scripts_table, interval=2.0):
    """Polls tmux for entries marked running; transitions them to stopped when the session ends."""
    while True:
        try:
            for name, info in list(scripts_table.items()):
                if info.get("status") != "running":
                    continue
                session = info["session"]
                has = subprocess.run(["tmux", "has-session", "-t", session], capture_output=True)
                if has.returncode != 0:
                    info["status"] = "stopped"
                    info["stopped_at"] = datetime.now().strftime("%Y%m%d_%H%M%S")
                    # Defensive: kill in case the session is in a stuck state.
                    subprocess.run(["tmux", "kill-session", "-t", session], capture_output=True)
                    logger.info(f"Script '{name}' detected as stopped.")
        except Exception as e:
            logger.error(f"scripts_watcher_loop iteration error: {e}")
        await asyncio.sleep(interval)

def kill_sitl_by_tag(tag_value):
    """
    Scans ALL system processes and kills those with the matching environment tag.
    """
    for proc in psutil.process_iter(['environ', 'name', 'pid']):
        try:
            # Check if our custom variable is in the process environment
            env = proc.info.get('environ')
            if env and env.get("UAV_SITL_TAG") == tag_value:
                logger.info(f"Found rogue process: {proc.info['name']} (PID: {proc.info['pid']}). Killing...")
                proc.kill() # Use kill() for xterms as they can be stubborn
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

def kill_tmux_sessions(prefix):
    """Kills all tmux sessions starting with the given prefix."""
    try:
        # Fetch a list of all active tmux session names
        result = subprocess.run(
            ['tmux', 'list-sessions', '-F', '#{session_name}'],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Split the output into a list of session names, ignoring empty strings
        sessions = [s for s in result.stdout.strip().split('\n') if s]
        
        killed_count = 0
        for session in sessions:
            if session.startswith(prefix):
                logger.info(f"Killing session: {session}...")
                subprocess.run(['tmux', 'kill-session', '-t', session])
                killed_count += 1

        if killed_count == 0:
            logger.info(f"No active tmux sessions found starting with '{prefix}'.")
        else:
            logger.info(f"Successfully killed {killed_count} session(s).")

    except subprocess.CalledProcessError:
        # tmux returns a non-zero exit status if the server isn't running
        logger.info("No active tmux server found. (No sessions to kill).")
    except FileNotFoundError:
        logger.error("Error: 'tmux' command not found. Ensure tmux is installed and in your PATH.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Configure loggers
    set_log_config(args)
    # Start SITL
    if args.simulated:
        logger.info("Starting SITL...")
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
        ardupilot_vehicle = "ArduPlane" if args.vehicle == "plane" else "ArduCopter"
        sitl_command = f"xterm -e {script_path} -v {ardupilot_vehicle} -I {args.sysid} --sysid {args.sysid} -N -L {args.location} --speedup {args.speedup} {out_str} --use-dir={ardupilot_logs}"
        
        # Start the process with the custom environment
        sitl_process = subprocess.Popen(sitl_command.split(" "), env=env)
        logger.info(f"SITL started with PID {sitl_process.pid}.")
    conn = args.uav_connection if args.connection_type == "usb" else f"{args.connection_type}:{args.uav_connection}"
    if args.vehicle == "plane":
        vehicle = get_plane_instance(args.sysid, conn)
    else:
        vehicle = get_copter_instance(args.sysid, conn)

    # Starting task that will continuously drain MAVLink messages
    logger.info("Starting Drain MAVLink loop...")
    drain_mav_loop = asyncio.create_task(vehicle.run_drain_mav_loop())

    # Scripts watcher (copter only — mission router is not registered for plane)
    scripts_watcher_task = None
    if args.vehicle != "plane":
        logger.info("Starting scripts watcher loop...")
        scripts_watcher_task = asyncio.create_task(scripts_watcher_loop(get_scripts_table()))

    # If defined, start location thread for Gradys Ground Station
    if args.gradys_gs is not None:
        logger.info("Starting Gradys GS location task...")
        session = aiohttp.ClientSession()
        location_task = asyncio.create_task(send_location_to_gradys_gs(vehicle, session, args.port, args.gradys_gs))
    
    logger.info("API is ready.")
    yield
    logger.info("Shutting down API...")

    logger.info("Closing tmux windows related to running scripts...")
    kill_tmux_sessions(f"UAV_API_{args.sysid}-")

    # Close SITL
    if args.simulated:
        logger.info("Closing SITL and all associated windows...")
        kill_sitl_by_tag(sitl_tag)
        logger.info("SITL and associated windows closed.")

    # Cancelling Drain Mav Loop Task
    logger.info("Cancelling Drain MAVLink loop...")
    drain_mav_loop.cancel()

    try:
        await drain_mav_loop
    except asyncio.CancelledError:
        logger.info("Drain MAVLink loop has been cancelled.")

    if scripts_watcher_task is not None:
        logger.info("Cancelling scripts watcher loop...")
        scripts_watcher_task.cancel()
        try:
            await scripts_watcher_task
        except asyncio.CancelledError:
            logger.info("Scripts watcher loop has been cancelled.")

    # Cancelling location coroutine if it was started
    if args.gradys_gs is not None:
        logger.info("Cancelling Gradys GS location task...")
        location_task.cancel()

        try:
            await location_task
        except asyncio.CancelledError:
            logger.info("Location task has been cancelled.")

        await session.close()
        logger.info("Gradys GS location task closed.")

    logger.info("UAV_API has shutdown gracefully.")