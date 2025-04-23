import os
import requests
import time

def start_drone(node_id, starting_position):
    node_id = int(node_id) + 10
    print(f"STARTING NODE {node_id}")

    os.system(f"python3 ./gradysim/uav_control/uav_api.py --simulated true --sysid {node_id} --port {8000+node_id} --uav_connection 127.0.0.1:17{171 + node_id} --speedup 2 --log_console COPTER --log_path ../../uav_logs&")
    
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
    
    return drone_url

def kill_drones():
    os.system("pkill -f uav_api.py")
    os.system("pkill xterm")