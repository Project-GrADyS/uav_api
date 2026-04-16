import sys
import os
import math
from time import sleep
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from flight_helpers import (
    add_common_args, get_base_url, create_session,
    send_command, setup_graceful_shutdown
)

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
add_common_args(parser)
parser.add_argument('--sides', type=int, nargs='+', default=[4])
parser.add_argument('--radius', type=int, default=10)
parser.add_argument('--height', type=int, default=20)
args = parser.parse_args()

# Ensures that the user defines a valid regular polygon
if 1 in args.sides or 2 in args.sides:
    print(f"Error: Polygon must have more than two sides!")
    exit()

# Failsafe: Ensure that the radius is smaller than the height of the perimeter's center
if args.radius >= args.height:
    print(f"Error: height vale must be higher then the radius value!")
    exit()

base_url = get_base_url(args)
session = create_session(args)
setup_graceful_shutdown(session, base_url)

# Arming vehicle
send_command(session, base_url, "/command/arm")
print("Vehicle armed.")

# Get the NED coordinates, from telemetry, of the initial position with the vehicle still on the ground
initial_result = send_command(session, base_url, "/telemetry/ned")
initial_pos = initial_result["info"]["position"]
print(f"Initial point: {initial_pos}")

# Taking off
send_command(session, base_url, "/command/takeoff", params={"alt": args.height})
print("Vehicle took off")

#sleep ensures the vehicle has time to reach its desired position
sleep(SLEEP_TIME)

# Get the NED coordinates, from telemetry, of the center of the polygons
center_result = send_command(session, base_url, "/telemetry/ned")
center_pos = center_result["info"]["position"]
print(f"center point: {center_pos}")

# Failsafe: Ensures the drone has reached the desired altitude, including a margin of error, if not it will land
if abs(center_pos["z"]-initial_pos["z"]) >= args.height+2 or abs(center_pos["z"]-initial_pos["z"]) <= args.height-2:
        print(f"Error: Vehicle did not reach the desired height.")
        send_command(session, base_url, "/command/land")
        print("Vehicle landed.")
        exit()

polygon_list = args.sides
for s in polygon_list:
    print(f"\n ---polygon {s}---------------------------------- \n")

    # For each polygon gets the NED coordinates of the vertices
    polygon_points = make_polygon_points(args.radius, s, center_pos)

    for point in polygon_points:
        # For each vertex moves the vehicle to its coordinate using go_to_ned_wait
        send_command(session, base_url, "/movement/go_to_ned_wait", params=point, method="POST")
        print(f"\nGo to point: {point})")

        #sleep ensures the vehicle has time to reach its desired position
        sleep(SLEEP_TIME)

        # Get the NED coordinates, from telemetry, of the vertex for better user visualization and debugging
        tele_ned_result = send_command(session, base_url, "/telemetry/ned")
        tele_ned_pos = tele_ned_result["info"]["position"]
        print(f"Vehicle at {tele_ned_pos})")

    # After completing the polygon, return the vehicle to the center using go_to_ned_wait
    send_command(session, base_url, "/movement/go_to_ned_wait", params=center_pos, method="POST")
    print(f"\nVehicle going back to the center")

    #sleep ensures the vehicle has time to reach its desired position
    sleep(SLEEP_TIME)

    print(f"Vehicle at the center")

# Landing
send_command(session, base_url, "/command/land")
print("\nVehicle landed.")
