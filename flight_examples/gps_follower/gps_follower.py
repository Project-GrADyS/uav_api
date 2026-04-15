import math
import time
import sys
import os
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from flight_helpers import (
    add_common_args, get_base_url, create_session,
    send_command, get_home_gps, setup_graceful_shutdown,
)


def parse_args():
    parser = argparse.ArgumentParser(description="GPS follower — tracks a leader drone with a configurable offset.")
    add_common_args(parser)
    parser.add_argument('--leader-url', type=str, default='localhost:8001',
                        help='Leader API host:port (default: localhost:8001)')
    parser.add_argument('--offset-north', type=float, default=-3,
                        help='North offset in meters; negative = behind (default: -3)')
    parser.add_argument('--offset-east', type=float, default=0,
                        help='East offset in meters (default: 0)')
    parser.add_argument('--offset-alt', type=float, default=2.0,
                        help='Altitude offset above leader in meters (default: 2.0)')
    return parser.parse_args()


def setup(session, base_url, leader_session, leader_base_url, altitude):
    """One-time setup: arm, capture home altitude, capture leader home altitude, and take off."""
    print("--- STARTING SETUP ---")

    # Arm the vehicle
    print("Arming the vehicle...")
    send_command(session, base_url, "/command/arm")

    # Capture home GPS after arming, before takeoff
    home = get_home_gps(session, base_url)
    home_alt = home[2]
    print(f"Follower home altitude captured: {home_alt:.1f}m")

    # Capture leader home GPS altitude (different barometer calibration)
    leader_home = get_home_gps(leader_session, leader_base_url)
    leader_home_alt = leader_home[2]
    print(f"Leader home altitude captured: {leader_home_alt:.1f}m")

    # Take off
    print(f"Taking off to {altitude}m...")
    send_command(session, base_url, "/command/takeoff", params={"alt": altitude})

    print("--- SETUP COMPLETE ---")
    return home_alt, leader_home_alt


def loop(session, base_url, leader_session, leader_base_url, home_alt, leader_home_alt, args):
    """Repeated loop: read leader position, compute offset, move follower."""
    try:
        # 1. Get the leader's GPS position
        data = send_command(leader_session, leader_base_url, "/telemetry/gps")
        l_pos = data["info"]["position"]

        leader_lat = float(l_pos["lat"])
        leader_lon = float(l_pos["lon"])
        leader_alt = float(l_pos["alt"])

        print(f"[Leader] Lat: {leader_lat:.6f}, Lon: {leader_lon:.6f}")

        # 2. Compute target position with offset (Haversine approximation)
        delta_lat = args.offset_north / 111111.0
        delta_lon = args.offset_east / (111111.0 * math.cos(math.radians(leader_lat)))

        target_lat = leader_lat + delta_lat
        target_lon = leader_lon + delta_lon

        leader_relative_alt = leader_alt - leader_home_alt
        raw_target_alt = leader_relative_alt + args.offset_alt
        target_alt = max(2.0, raw_target_alt)

        # 3. Send go-to-GPS command to the follower
        fly_data = {
            "lat": target_lat,
            "long": target_lon,
            "alt": target_alt,
        }
        send_command(session, base_url, "/movement/go_to_gps", params=fly_data, method="POST")

        print(f">> Moving follower to: {target_lat:.6f}, {target_lon:.6f}, alt={target_alt:.1f}m")

    except Exception as e:
        print(f"Loop error: {e}")

    # Update rate: 2 Hz
    time.sleep(0.5)


if __name__ == "__main__":
    args = parse_args()

    # Build base URLs for follower and leader with matching scheme
    follower_base_url = get_base_url(args)

    scheme = "https" if args.h3 else "http"
    leader_base_url = f"{scheme}://{args.leader_url}"

    # Create HTTP sessions (both use the same TLS settings when --h3 is set)
    follower_session = create_session(args)
    leader_session = create_session(args)

    # Register Ctrl+C handler — sends RTL to the follower before exiting
    setup_graceful_shutdown(follower_session, follower_base_url)

    home_alt, leader_home_alt = setup(follower_session, follower_base_url,
                                      leader_session, leader_base_url, args.altitude)

    print("\n--- FOLLOWING LEADER (Ctrl+C to RTL and exit) ---\n")
    while True:
        loop(follower_session, follower_base_url,
             leader_session, leader_base_url, home_alt, leader_home_alt, args)
