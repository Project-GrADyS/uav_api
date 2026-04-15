"""Takeoff and land — the simplest flight example."""

import sys
import os
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from flight_helpers import add_common_args, get_base_url, create_session, send_command, setup_graceful_shutdown

parser = argparse.ArgumentParser(description="Arm, take off, and land.")
add_common_args(parser)
args = parser.parse_args()

base_url = get_base_url(args)
session = create_session(args)
setup_graceful_shutdown(session, base_url)

# Arm
send_command(session, base_url, "/command/arm")
print("Vehicle armed.")

# Take off
send_command(session, base_url, "/command/takeoff", params={"alt": args.altitude})
print(f"Vehicle took off to {args.altitude}m.")

# Land
send_command(session, base_url, "/command/land")
print("Vehicle landed.")
