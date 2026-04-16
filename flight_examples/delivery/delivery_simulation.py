"""Delivery simulation: pickup a package, fly to delivery point, return home.

Mission flow:
  1. Arm and take off to safe altitude.
  2. Fly to pickup location, land, simulate package pickup.
  3. Arm, take off, fly to delivery location, land, simulate package drop.
  4. Arm, take off, return to home, land.

Coordinates are home-relative NED (North, East, Down). A SAFE_OFFSET is added
to the Down component during navigation for safe cruise altitude.
"""

import sys
import os
import time
import argparse

# Allow importing flight_helpers from the parent directory
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
    euclidean_distance,
)

SLEEP_DURATION = 4  # seconds between commands
TAKEOFF_ALTITUDE = 5  # meters AGL
SAFE_OFFSET = -2  # extra Down offset for safe cruise altitude


def parse_ned(s):
    """Parse a 'N,E,D' string into a tuple of three floats."""
    parts = tuple(map(float, s.split(",")))
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(f"Expected N,E,D format, got: {s}")
    return parts


def ensure_negative_altitude(ned):
    """Ensure the Down component is negative (above ground in NED)."""
    if ned[2] >= 0:
        print("Altitude must be negative in NED coordinates. Adjusted to negative value.")
        return (ned[0], ned[1], -abs(ned[2]))
    return ned


def go_to_relative(session, base_url, relative, home):
    """Navigate to a home-relative NED point with SAFE_OFFSET applied to Down."""
    target_abs = (
        relative[0] + home[0],
        relative[1] + home[1],
        relative[2] + home[2] + SAFE_OFFSET,
    )
    send_command(session, base_url, "/movement/go_to_ned",
                 params={"x": target_abs[0], "y": target_abs[1], "z": target_abs[2]},
                 method="POST")
    return target_abs


# --- Argument parsing ---
parser = argparse.ArgumentParser(
    description="Simulate a drone delivery: home -> pickup -> delivery -> home."
)
add_common_args(parser)
parser.add_argument("--pickup", type=str, default="10,0,-5",
                    help="Pickup location as N,E,D (default: 10,0,-5)")
parser.add_argument("--delivery", type=str, default="0,10,-5",
                    help="Delivery location as N,E,D (default: 0,10,-5)")
args = parser.parse_args()

pickup_location = ensure_negative_altitude(parse_ned(args.pickup))
delivery_location = ensure_negative_altitude(parse_ned(args.delivery))

base_url = get_base_url(args)
session = create_session(args)
setup_graceful_shutdown(session, base_url)

# --- Mission start ---
print(f"\nPickup:   {pickup_location}")
print(f"Delivery: {delivery_location}")

# Arm
print("Arming...")
send_command(session, base_url, "/command/arm")
time.sleep(SLEEP_DURATION)

# Get home location after arming, before takeoff
home = get_home_ned(session, base_url)
time.sleep(SLEEP_DURATION)

print(f"Takeoff to {TAKEOFF_ALTITUDE}m...")
send_command(session, base_url, "/command/takeoff", params={"alt": TAKEOFF_ALTITUDE})
time.sleep(SLEEP_DURATION)

# --- Leg 1: Home -> Pickup ---
print(f"Going to pickup location: {pickup_location}")
target_abs = go_to_relative(session, base_url, pickup_location, home)
time.sleep(SLEEP_DURATION)

if wait_for_arrival(session, base_url, target_abs):
    print("Drone arrived at pickup location.")
time.sleep(SLEEP_DURATION)

print("Landing to pick up package...")
send_command(session, base_url, "/command/land")
time.sleep(SLEEP_DURATION)

# Simulated package pickup
time.sleep(SLEEP_DURATION)

# Arm and take off again
print("Arming...")
send_command(session, base_url, "/command/arm")
time.sleep(SLEEP_DURATION)

print(f"Takeoff to {TAKEOFF_ALTITUDE}m...")
send_command(session, base_url, "/command/takeoff", params={"alt": TAKEOFF_ALTITUDE})
time.sleep(SLEEP_DURATION)

# --- Leg 2: Pickup -> Delivery ---
print(f"Going to delivery location: {delivery_location}")
target_abs = go_to_relative(session, base_url, delivery_location, home)
time.sleep(SLEEP_DURATION)

if wait_for_arrival(session, base_url, target_abs):
    print("Drone arrived at delivery location.")
time.sleep(SLEEP_DURATION)

print("Landing to deliver package...")
send_command(session, base_url, "/command/land")
time.sleep(SLEEP_DURATION)

# Simulated package drop
time.sleep(SLEEP_DURATION)

# Arm and take off again
print("Arming...")
send_command(session, base_url, "/command/arm")
time.sleep(SLEEP_DURATION)

print(f"Takeoff to {TAKEOFF_ALTITUDE}m...")
send_command(session, base_url, "/command/takeoff", params={"alt": TAKEOFF_ALTITUDE})
time.sleep(SLEEP_DURATION)

# --- Leg 3: Delivery -> Home ---
home_relative = (0, 0, 0)
print(f"Returning to home...")
target_abs = go_to_relative(session, base_url, home_relative, home)
time.sleep(SLEEP_DURATION)

if wait_for_arrival(session, base_url, target_abs):
    print("Drone arrived near home location.")
time.sleep(SLEEP_DURATION)

print("Landing at home location...")
send_command(session, base_url, "/command/land")
time.sleep(SLEEP_DURATION)

print("Mission accomplished.")
