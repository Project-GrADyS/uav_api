import math
import time
import sys
import argparse


def add_common_args(parser):
    """Add standard arguments shared by all flight examples."""
    parser.add_argument('--url', type=str, default='localhost:8000',
                        help='API host:port (default: localhost:8000)')
    parser.add_argument('--altitude', type=float, default=10,
                        help='Takeoff altitude in meters (default: 10)')
    parser.add_argument('--h3', action='store_true', default=False,
                        help='Use HTTP/3 over QUIC (requires niquests and TLS certs)')
    parser.add_argument('--certfile', type=str, default='~/uav_api_certs/dev-cert.pem',
                        help='TLS certificate path for HTTP/3 (default: ~/uav_api_certs/dev-cert.pem)')
    return parser


def get_base_url(args):
    """Return the base URL with correct scheme based on --h3 flag."""
    scheme = "https" if args.h3 else "http"
    return f"{scheme}://{args.url}"


def create_session(args):
    """Create an HTTP session — requests.Session or niquests.Session for H3."""
    if args.h3:
        import niquests
        import os
        certfile = os.path.expanduser(args.certfile)
        session = niquests.Session(timeout=(5, 120))
        session.verify = certfile
        return session
    else:
        import requests
        return requests.Session()


def send_command(session, base_url, endpoint, params=None, method="GET"):
    """Send a command to the drone API and return the JSON response."""
    url = f"{base_url}{endpoint}"
    try:
        if method == "GET":
            response = session.get(url, params=params)
        elif method == "POST":
            response = session.post(url, json=params)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        if response.status_code != 200:
            print(f"Command {endpoint} failed. status_code={response.status_code}")
            sys.exit(1)
        return response.json()
    except Exception as e:
        print(f"HTTP request failed: {e}")
        sys.exit(1)


def euclidean_distance(p1, p2):
    """Calculate 3D Euclidean distance between two (x, y, z) tuples."""
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2 + (p1[2] - p2[2])**2)


def wait_for_arrival(session, base_url, target, tolerance=1.0, timeout=120):
    """Poll /telemetry/ned until the drone is within tolerance of target (absolute NED coords).

    Returns True if arrived, False if timed out.
    """
    start = time.time()
    while time.time() < start + timeout:
        ned = send_command(session, base_url, "/telemetry/ned")
        pos = ned["info"]["position"]
        current = (pos["x"], pos["y"], pos["z"])
        dist = euclidean_distance(target, current)
        print(f"  Position: ({current[0]:.1f}, {current[1]:.1f}, {current[2]:.1f}), "
              f"distance to target: {dist:.2f}m")
        if dist < tolerance:
            return True
        time.sleep(1)
    print(f"  Timeout: did not reach target within {timeout}s")
    return False


def get_home_ned(session, base_url):
    """Capture the current NED position as home reference (call after arming, before takeoff)."""
    result = send_command(session, base_url, "/telemetry/ned")
    pos = result["info"]["position"]
    home = (pos["x"], pos["y"], pos["z"])
    print(f"Home NED position: ({home[0]:.1f}, {home[1]:.1f}, {home[2]:.1f})")
    return home


def get_home_gps(session, base_url):
    """Capture the current GPS position as home reference (call after arming, before takeoff)."""
    result = send_command(session, base_url, "/telemetry/gps")
    pos = result["info"]["position"]
    home = (float(pos["lat"]), float(pos["lon"]), float(pos["alt"]))
    print(f"Home GPS position: lat={home[0]:.6f}, lon={home[1]:.6f}, alt={home[2]:.1f}m")
    return home


def ned_relative_to_absolute(relative, home):
    """Convert a home-relative NED tuple to absolute NED coordinates."""
    return (relative[0] + home[0], relative[1] + home[1], relative[2] + home[2])


def setup_graceful_shutdown(session, base_url):
    """Register a Ctrl+C handler that sends RTL before exiting."""
    import signal

    def handler(signum, frame):
        print("\n--- Ctrl+C detected — sending RTL ---")
        try:
            send_command(session, base_url, "/command/rtl")
        except Exception:
            pass
        print("Exiting.")
        sys.exit(0)

    signal.signal(signal.SIGINT, handler)
