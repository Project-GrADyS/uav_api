import requests
import math
from time import sleep
import argparse
base_url = "http://localhost:8000"

SLEEP_TIME = 5

def make_polygon_points(r, s, offset):
    points = []
    for v in range(s):
        point = {
            "x": r*math.sin(v*2*math.pi/s) + offset["x"],
            "y": offset["y"],
            "z": -(r*math.cos(v*2*math.pi/s)) + offset["z"]
        }
        print(f"polygon point {v}: {point}")
        points.append(point)
    return(points)

# Get the user's arguments
parser = argparse.ArgumentParser()
parser.add_argument('--sides', type=int, nargs='+', required=True)
parser.add_argument('--radius', type=int, required=True)
parser.add_argument('--height', type=int, required=True)
args = parser.parse_args()

# Ensures that the user defines a valid regular polygon
if 1 in args.sides or 2 in args.sides:
    print(f"Error: Polygon must have more than two sides!")
    exit()

# Failsafe: Ensure that the radius is smaller than the height of the perimeter's center
if args.radius >= args.height:
    print(f"Error: height vale must be higher then the radius value!")
    exit()

# Arming vehicle
arm_result = requests.get(f"{base_url}/command/arm")
if arm_result.status_code != 200:
    print(f"Arm command fail. status_code={arm_result.status_code}")
    exit()
print("Vehicle armed.")

# Get the NED coordinates, from telemetry, of the initial position with the vehicle still on the ground
initial_result = requests.get(f"{base_url}/telemetry/ned")
if initial_result.status_code != 200:
    print(f"Ned telemetry fail. status_code={initial_result.status_code}")
    exit()
initial_pos = initial_result.json()["info"]["position"]
print(f"Initial point: {initial_pos}")

# Taking off
params = {"alt": args.height}
takeoff_result = requests.get(f"{base_url}/command/takeoff", params=params)
if takeoff_result.status_code != 200:
    print(f"Take off command fail. status_code={takeoff_result.status_code}")
    exit()
print("Vehicle took off")

#sleep ensures the vehicle has time to reach its desired position
sleep(SLEEP_TIME)

# Get the NED coordinates, from telemetry, of the center of the polygons
center_result = requests.get(f"{base_url}/telemetry/ned")
if center_result.status_code != 200:
    print(f"Ned telemetry fail. status_code={center_result.status_code}")
    exit()
center_pos = center_result.json()["info"]["position"]
print(f"center point: {center_pos}")

# Failsafe: Ensures the drone has reached the desired altitude, including a margin of error, if not it will land
if abs(center_pos["z"]-initial_pos["z"]) >= args.height+2 or abs(center_pos["z"]-initial_pos["z"]) <= args.height-2:
        print(f"Error: Vehicle did not reach the desired height.")
        land_result = requests.get(f"{base_url}/command/land")
        if land_result.status_code != 200:
            print(f"Land command fail. status_code={land_result.status_code}")
            exit()
        print("Vehicle landed.")
        exit()

polygon_list = args.sides
for s in polygon_list:
    print(f"\n ---polygon {s}---------------------------------- \n")

    # For each polygon gets the NED coordinates of the vertices
    polygon_points = make_polygon_points(args.radius, s, center_pos)
        
    for point in polygon_points:
        # For each vertex moves the vehicle to its coordinate using go_to_ned_wait
        point_result = requests.post(f"{base_url}/movement/go_to_ned_wait", json=point)
        if point_result.status_code != 200:
            print(f"Go_to_ned_wait command fail. status_code={point_result.status_code} point={point}")
            exit()
        print(f"\nGo to point: {point})")

        #sleep ensures the vehicle has time to reach its desired position
        sleep(SLEEP_TIME)

        # Get the NED coordinates, from telemetry, of the vertex for better user visualization and debugging
        tele_ned_result = requests.get(f"{base_url}/telemetry/ned")
        if tele_ned_result.status_code != 200:
            print(f"Ned telemetry fail. status_code={tele_ned_result.status_code}")
            exit()
        tele_ned_pos = tele_ned_result.json()["info"]["position"]
        print(f"Vehicle at {tele_ned_pos})")

    # After completing the polygon, return the vehicle to the center using go_to_ned_wait
    point_result = requests.post(f"{base_url}/movement/go_to_ned_wait", json=center_pos)
    if point_result.status_code != 200:
        print(f"Go_to_ned_wait command fail. status_code={point_result.status_code} point={center_pos}")
        exit()
    print(f"\nVehicle going back to the center")

    #sleep ensures the vehicle has time to reach its desired position
    sleep(SLEEP_TIME)
    
    print(f"Vehicle at the center")

# Landing
land_result = requests.get(f"{base_url}/command/land")
if land_result.status_code != 200:
    print(f"Land command fail. status_code={land_result.status_code}")
    exit()
print("\nVehicle landed.")
