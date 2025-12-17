import requests
import math
from time import sleep
import argparse
base_url = "http://localhost:8000"

SLEEP_TIME = 5

def make_poligon_trajectory(r, l):
    vectors = []
    for n in range(l):
        if n == 0:
            vector = {
                "x": 0,
                "y": 0,
                "z": -1
            }
        else:
            vector = {
                "x": round(r*math.sin(n*2*math.pi/l) - r*math.sin((n-1)*2*math.pi/l)),
                "y": 0,
                "z": -(round(r*math.cos(n*2*math.pi/l) - r*math.cos((n-1)*2*math.pi/l)))
            }
        print(f"poligon vector {n}: {vector}")
        vectors.append(vector)

    return(vectors)

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

poligon_list = args.sides
for l in poligon_list:
    print(f"\n ---Poligon {l}---------------------------------- \n")

    # For each polygon gets the NED trajectory vectors to the vertices
    poligon_trajectory = make_poligon_trajectory(args.radius, l)
        
    # Moving
    for vector in poligon_trajectory:
        # For each vertex moves the vehicle along its trajectory using drive_wait
        vector_result = requests.post(f"{base_url}/movement/drive_wait", json=vector)
        if vector_result.status_code != 200:
            print(f"Drive_wait command fail. status_code={vector_result.status_code} vector={vector}")
            exit()
        print(f"\nTrajectory vector: {vector})")

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
