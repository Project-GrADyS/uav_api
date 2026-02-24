#Objective: Control a drone via Python to simulate a delivery.
#The drone picks up the package, goes to the delivery point, lands,
#disarms, simulates/drops an actuator, arms, takes off, and returns to first takeoff point (home).

#Steps:
# 1. Receive pickup and delivery locations as NED points via command line arguments.
# 2. Get home location from drone telemetry.
# 3. Arm and take off to a safe altitude.
# 4. Navigate to pickup location, land, disarm, simulate package pickup.
# 5. Arm, take off to a safe altitude, navigate to delivery location, land, disarm, simulate package drop.
# 6. Arm, take off to a safe altitude, return to home location, land.

#Observations:
# - A -2 meter offset is applied to the Down NED points for safe altitude during navigation.
# - Takeoff altitude is set to 5 meters above ground level.

import sys #sys module to handle command line arguments
import requests #requests module to make HTTP requests
import time #time module to handle sleep and timeouts
import math #math module for distance calculations

BASE_URL = "http://localhost:8000" # Base URL for the drone API
SLEEP_DURATION = 4 #variable to adjust sleep duration between commands
TAKEOFF_ALTITUDE = 5 # Safe takeoff altitude in meters
SAFE_OFFSET = -2 # Safe offset in Down NED coordinate in meters

# Function to send commands to the drone API
def send_command(endpoint, params=None, method="GET"):
    url = f"{BASE_URL}{endpoint}"
    try:
        if method == "GET":
            response = requests.get(url, params=params)
        elif method == "POST":
            response = requests.post(url, json=params)
        else:
            raise ValueError("Unsupported HTTP method")

        if response.status_code != 200:
            print(f"Command {endpoint} failed. status_code={response.status_code}")
            exit()
        return response.json()
    except requests.RequestException as e:
        print(f"HTTP request failed: {e}")
        exit()

# Function to calculate distance between two NED points
def distance(end, start):
    return math.sqrt((end[0]-start[0])**2 + (end[1]-start[1])**2 + ((end[2] + SAFE_OFFSET)-start[2])**2)

# Function to wait until the drone arrives at a specified location within a tolerance and timeout
def wait_for_arrival(location, tolerance=1.0, timeout=120):
    start = time.time()
    while time.time() < start + timeout:
        ned_result = requests.get(f"{BASE_URL}/telemetry/ned")
        if ned_result.status_code != 200:
            print(f"NED telemetry fail. status_code={ned_result.status_code}")
            exit()
        ned_pos = ned_result.json()["info"]["position"]
        ned_point = (ned_pos["x"]-home_location[0], ned_pos["y"]-home_location[1], ned_pos["z"]-home_location[2])
        dist = distance(location, ned_point)
        print(f"Current position: {ned_point}, distance to target: {dist:.2f} m")
        if dist < tolerance:
            return True
        time.sleep(2)
    return False



#Recieve package and delivery locations via command line format: N,E,D N,E,D
if len(sys.argv) == 1: #if no arguments are provided, default locations are used
    pickup_location = (1, 3, -3) #Default pickup location
    delivery_location = (0, 2, -3) #Default delivery location
    print("No command line arguments provided. Using default locations.")
elif len(sys.argv) != 3: #Invalid number of arguments
    print("Usage: python t3.py <pickup_location> <delivery_location>")
    exit()
else: #Parse command line arguments
    try:
        pickup_location = tuple(map(float, sys.argv[1].split(',')))
        delivery_location = tuple(map(float, sys.argv[2].split(',')))
        if len(pickup_location) != 3 or len(delivery_location) != 3: # Check for correct number of coordinates
            raise ValueError
    except ValueError:
        print("Invalid location format. Use N(orth),E(ast),D(own)")
        exit()
# Ensure altitudes are negative in NED coordinates
if pickup_location[2] >= 0 or delivery_location[2] >= 0:
    pickup_location = (pickup_location[0], pickup_location[1], -abs(pickup_location[2]))
    delivery_location = (delivery_location[0], delivery_location[1], -abs(delivery_location[2]))
    print("Altitude must be negative in NED coordinates. Adjusted to negative values.")

# Start
print("\nNED points received: ", pickup_location, delivery_location)
# Get home location
print("Getting home location based on NED telemetry of EKF origin...")
home = send_command("/telemetry/ned")["info"]["position"]
home_location = (home["x"], home["y"], home["z"])
print("Home location at NED point: ", home_location)
time.sleep(SLEEP_DURATION) # Sleep to ensure commands are spaced out

print("Arming...")
send_command("/command/arm")
time.sleep(SLEEP_DURATION)

print("Takeoff...")
send_command("/command/takeoff", params={"alt": TAKEOFF_ALTITUDE})
time.sleep(SLEEP_DURATION)

# Pickup location
#default pickup_location = (1, 3, -3)
print("Going to pickup location at NED point: ", pickup_location)
send_command("/movement/go_to_ned", params={"x": pickup_location[0]+home_location[0],
                                            "y": pickup_location[1]+home_location[1],
                                            "z": pickup_location[2]+home_location[2]+SAFE_OFFSET},
                                            method="POST")
time.sleep(SLEEP_DURATION)

print(pickup_location)
if wait_for_arrival(pickup_location):
    print("Drone arrived at pickup location")
time.sleep(SLEEP_DURATION)


print("Landing to pick up package...")
send_command("/command/land")
time.sleep(SLEEP_DURATION)

current_ned = send_command("/telemetry/ned")["info"]["position"]
current_ned_point = (current_ned["x"]-home_location[0],
                     current_ned["y"]-home_location[1],
                     current_ned["z"]-home_location[2])
print("Current NED position after landing: ", current_ned_point)
time.sleep(SLEEP_DURATION)

print("Disarming...")
print("Simulating package pickup...")
# simulated pick up
time.sleep(SLEEP_DURATION)

print("Arming...")
send_command("/command/arm")
time.sleep(SLEEP_DURATION)

print("Takeoff...")
send_command("/command/takeoff", params={"alt": TAKEOFF_ALTITUDE})
time.sleep(SLEEP_DURATION)

# Delivery location
#default delivery_location = (0, 2, -3)
print("Going to delivery location at NED point: ", delivery_location)
send_command("/movement/go_to_ned", params={"x": delivery_location[0]+home_location[0],
                                            "y": delivery_location[1]+home_location[1],
                                            "z": delivery_location[2]+home_location[2]+SAFE_OFFSET},
                                            method="POST")
time.sleep(SLEEP_DURATION)

print(delivery_location)
if wait_for_arrival(delivery_location):
    print("Drone arrived at delivery location")
time.sleep(SLEEP_DURATION)

print("Landing to deliver package...")
send_command("/command/land")
time.sleep(SLEEP_DURATION)

current_ned = send_command("/telemetry/ned")["info"]["position"]
current_ned_point = (current_ned["x"]-home_location[0],
                     current_ned["y"]-home_location[1],
                     current_ned["z"]-home_location[2])
print("Current NED position after landing: ", current_ned_point)
time.sleep(SLEEP_DURATION)

print("Disarming...")
print("Simulating package drop...")
# simulated drop
time.sleep(SLEEP_DURATION)

print("Arming...")
send_command("/command/arm")
time.sleep(SLEEP_DURATION)

print("Takeoff...")
send_command("/command/takeoff", params={"alt": TAKEOFF_ALTITUDE})
time.sleep(SLEEP_DURATION)

print("Returning to Home at NED point: ", home_location)
send_command("/movement/go_to_ned", params={"x": home_location[0],
                                            "y": home_location[1],
                                            "z": home_location[2]+SAFE_OFFSET},
                                            method="POST")
time.sleep(SLEEP_DURATION)

if wait_for_arrival(0,0,0):
    print("Drone arrived near Home location")
time.sleep(SLEEP_DURATION)

print("landing at Home location...")
send_command("/command/land")
time.sleep(SLEEP_DURATION)

current_ned = send_command("/telemetry/ned")["info"]["position"]
current_ned_point = (current_ned["x"]-home_location[0],
                     current_ned["y"]-home_location[1],
                     current_ned["z"]-home_location[2])
print("Current NED position after landing: ", current_ned_point)

print("Mission Accomplished")
