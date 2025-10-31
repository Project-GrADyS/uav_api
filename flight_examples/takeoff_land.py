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

# Landing...
land_result = requests.get(f"{base_url}/command/land")
if land_result.status_code != 200:
    print(f"Land command fail. status_code={land_result.status_code}")
    exit()
print("Vehicle landed.")