import sys
import os
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from flight_helpers import (
    add_common_args,
    get_base_url,
    create_session,
    send_command,
    get_home_ned,
    ned_relative_to_absolute,
    wait_for_arrival,
    setup_graceful_shutdown,
)

parser = argparse.ArgumentParser(description="Fly a square pattern using NED coordinates (polling version).")
add_common_args(parser)
parser.add_argument('--side', type=float, default=20,
                    help='Side length of the square in meters (default: 20)')
args = parser.parse_args()

base_url = get_base_url(args)
session = create_session(args)
setup_graceful_shutdown(session, base_url)

# Arm vehicle
send_command(session, base_url, "/command/arm")
print("Vehicle armed.")

# Capture home NED position after arming, before takeoff
home = get_home_ned(session, base_url)

# Take off
send_command(session, base_url, "/command/takeoff", params={"alt": args.altitude})
print(f"Vehicle took off to {args.altitude}m.")

# Define square waypoints as relative offsets from home
side = args.side
alt = -args.altitude
relative_points = [
    (side, side, alt),
    (side, -side, alt),
    (-side, -side, alt),
    (-side, side, alt),
]

# Fly the square using non-blocking go_to_ned + polling
for i, rel in enumerate(relative_points, start=1):
    absolute = ned_relative_to_absolute(rel, home)
    point_data = {"x": absolute[0], "y": absolute[1], "z": absolute[2]}
    print(f"\nWaypoint {i}: sending go_to_ned -> ({absolute[0]:.1f}, {absolute[1]:.1f}, {absolute[2]:.1f})")
    send_command(session, base_url, "/movement/go_to_ned", params=point_data, method="POST")
    arrived = wait_for_arrival(session, base_url, absolute, tolerance=1.0, timeout=120)
    if arrived:
        print(f"Waypoint {i}: arrived.")
    else:
        print(f"Waypoint {i}: timed out — aborting, sending RTL.")
        send_command(session, base_url, "/command/rtl")
        exit(1)

# Return to launch
send_command(session, base_url, "/command/rtl")
print("\nSquare complete — vehicle returning to launch.")
