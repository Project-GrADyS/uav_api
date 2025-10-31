import requests
base_url = "http://localhost:8000"

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
    point_result = requests.post(f"{base_url}/movement/go_to_ned_wait", json=point_data)
    if point_result.status_code != 200:
        print(f"Go_to_ned_wait command fail. status_code={point_result.status_code} point={point}")
        exit()
    print(f"Vehicle at ({point[0]}, {point[1]}, {point[2]})")

# Returning to launch
rtl_result = requests.get(f"{base_url}/command/rtl")
if rtl_result.status_code != 200:
    print(f"RTL command fail. status_code={rtl_result.status_code}")
    exit()
print("Vehicle landed at launch.")