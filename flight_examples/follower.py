import requests
from time import sleep, time

base_url = "http://localhost:8001"
leader_url = "http://localhost:8000"
# Arming vehicle
arm_result = requests.get(f"{base_url}/command/arm")
if arm_result.status_code != 200:
    print(f"Arm command fail. status_code={arm_result.status_code}")
    exit()
print("Vehicle armed.")

# Taking off
params = {"alt": 20}
takeoff_result = requests.get(f"{base_url}/command/takeoff", params=params)
if takeoff_result.status_code != 200:
    print(f"Take off command fail. status_code={takeoff_result.status_code}")
    exit()
print("Vehicle took off")

# Follow leader for 30 seconds
start_time = time()
current_time = time()
while (current_time - start_time) <= 30:
    leader_telemetry_result = requests.get(f"{leader_url}/telemetry/ned")
    if leader_telemetry_result.status_code != 200:
        print(f"Leader telemetry fail. status_code={leader_telemetry_result.status_code}")
        exit()
    leader_pos = leader_telemetry_result.json()["info"]["position"]

    print("Got leader telemetry.")

    movement_data = {
        "x": leader_pos["x"] + 5,
        "y": leader_pos["y"] + 5,
        "z": -20
    }
    movement_result = requests.post(f"{base_url}/movement/go_to_ned", json=movement_data)
    if movement_result.status_code != 200:
        print(f"Follower go to ({movement_data['x']}, {movement_data['y']}, {movement_data['z']}) failed. status_code={movement_result.status_code}")
        exit()
    
    print(f"Follower going to ({movement_data['x']}, {movement_data['y']}, {movement_data['z']}).")

    sleep(2)
    current_time = time()

# Return to launch
print("Returning to launch...")
rtl_result = requests.get(f"{base_url}/command/rtl")
if rtl_result.status_code != 200:
    print(f"RTL command fail. status_code={rtl_result.status_code}")
    exit()

print("Landed at launch")