import requests
import time
import math

base_url = "http://localhost:8000"

def euclidean_distance(point1, point2):
    return math.sqrt((point1[0] - point2[0])**2 + (point1[1] - point2[1])**2 + (point1[2] - point2[2])**2)

def wait_for_point(point, max_error, timeout):
    start = time.time()
    while time.time() < start + timeout:
        ned_result = requests.get(f"{base_url}/telemetry/ned")
        if ned_result.status_code != 200:
            print(f"Ned telemetry fail. status_code={ned_result.status_code}")
            exit()
        ned_pos = ned_result.json()["info"]["position"]
        print(ned_pos)
        ned_point = (ned_pos["x"], ned_pos["y"], ned_pos["z"])
        distance = euclidean_distance(point, ned_point)
        if distance < max_error:
            return True
    return False


# Arming vehicle
arm_result = requests.get(f"{base_url}/command/arm")
if arm_result.status_code != 200:
    print(f"Arm command fail. status_code={arm_result.status_code}")
    exit()
print("Vehicle armed.")

# Taking off
params = {"alt": 30}
takeoff_result = requests.get(f"{base_url}/command/takeoff", params=params)
if takeoff_result.status_code != 200:
    print(f"Take off command fail. status_code={takeoff_result.status_code}")
    exit()
print("Vehicle took off")

square_points = [
    (100, 100, -50),
    (100, -100, -50),
    (-100, -100, -50),
    (-100, 100, -50)
]

# Moving
for point in square_points:
    point_data = {
        "x": point[0],
        "y": point[1],
        "z": point[2]
    }
    point_result = requests.post(f"{base_url}/movement/go_to_ned", json=point_data)
    if point_result.status_code != 200:
        print(f"Go_to_ned command fail. status_code={point_result.status_code} point={point}")
        exit()

    arrived = wait_for_point(point, max_error=3, timeout=60)
    if not arrived:
        print(f"Error while going to point {point}")
        exit()
    print(f"Vehicle at ({point[0]}, {point[1]}, {point[2]})")

# Returning to launch
rtl_result = requests.get(f"{base_url}/command/rtl")
if rtl_result.status_code != 200:
    print(f"RTL command fail. status_code={rtl_result.status_code}")
    exit()
print("Vehicle landed at launch.")