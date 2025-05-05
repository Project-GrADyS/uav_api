import os
import requests
import time

from uav_api.run_api import run_with_args
from multiprocessing import Process

def start_drone(node_id, starting_position):
    node_id = int(node_id) + 10
    print(f"STARTING NODE {node_id}")

    raw_args = ['--simulated', 'true', '--sysid', f'{node_id}', '--port', f'{8000+node_id}', '--uav_connection', f'127.0.0.1:17{171+node_id}', '--speedup', '1', '--log_console', 'COPTER', '--log_path', '../../uav_logs']

    api_process = run_with_args(raw_args)
    print(f"[NODE-{node_id}] API process started.")
    
    drone_url = f"http://localhost:{8000+node_id}"

    time.sleep(5)  # Wait for the drone API to start

    print(f"[NODE-{node_id}] Arming...")
    arm_result = requests.get(f"{drone_url}/command/arm")
    if arm_result.status_code != 200:
        raise(f"[NODE-{node_id}] Failed to arm drone.")
    print("[NODE-{node_id}] Arming complete.")
    
    print(f"[NODE-{node_id}] Taking off...")
    takeoff_result = requests.get(f"{drone_url}/command/takeoff", params={"alt": 10})
    if takeoff_result.status_code != 200:
        raise("[NODE-{node_id}] Failed to take off.")
    print(f"[NODE-{node_id}] Takeoff complete.")

    print(f"[NODE-{node_id}] Going to start position...")
    pos_data = {"x": starting_position[0], "y": starting_position[1], "z": -starting_position[2]} # in this step we buld the json data and convert z in protocol frame to z in ned frame (downwars)
    go_to_result = requests.post(f"{drone_url}/movement/go_to_ned_wait", json=pos_data)
    if go_to_result.status_code != 200:
        raise(f"[NODE-{node_id}] Failed to go to start position.")
    print(f"[NODE-{node_id}] Go to start position complete.")
    
    return (drone_url, api_process)

def kill_drones(drone_process):
    for process in drone_process:
        process.terminate()