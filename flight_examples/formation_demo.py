import subprocess
import sys
import os
import time
import math
import signal
import tempfile
import argparse
import requests

# --- GLOBALS ---
uav_api_processes = []
formation_processes = []
config_dir = None

NUM_DRONES = 6
NUM_FOLLOWERS = 5
MASTER_INDEX = 6  # Master is drone 6
MASTER_PORT = 8006
MASTER_URL = f"http://localhost:{MASTER_PORT}"
TAKEOFF_ALT = 20

def parse_args():
    parser = argparse.ArgumentParser(description="Formation demo: 5 drones in pentagon around a master flying a square")
    parser.add_argument("--ardupilot_path", type=str, default="~/ardupilot",
                        help="Path to ArduPilot repository")
    parser.add_argument("--square_size", type=float, default=50,
                        help="Side length of master's square path in meters")
    parser.add_argument("--radius", type=float, default=10,
                        help="Formation polygon radius in meters")
    parser.add_argument("--speedup", type=int, default=1,
                        help="SITL simulation speedup")
    parser.add_argument("--orientation", type=str, default="horizontal",
                        choices=["horizontal", "vertical"],
                        help="Formation polygon orientation")
    return parser.parse_args()


def generate_configs(ardupilot_path, speedup):
    """Generate INI config files for all 6 UAVs in a temp directory."""
    global config_dir
    config_dir = tempfile.mkdtemp(prefix="formation_demo_")
    configs = []

    for i in range(1, NUM_DRONES + 1):
        config_path = os.path.join(config_dir, f"uav_{i}.ini")
        content = (
            f"[api]\n"
            f"port={8000 + i}\n"
            f"uav_connection=127.0.0.1:{17170 + i}\n"
            f"connection_type=udpin\n"
            f"sysid={i}\n"
            f"\n"
            f"[simulated]\n"
            f"location=AbraDF\n"
            f"ardupilot_path={ardupilot_path}\n"
            f"speedup={speedup}\n"
        )
        with open(config_path, "w") as f:
            f.write(content)
        configs.append(config_path)

    return configs


def launch_uav_apis(configs):
    """Launch 6 uav-api instances as background processes."""
    for i, config_path in enumerate(configs):
        print(f"Launching uav-api instance {i + 1} (port {8001 + i})...")
        log_file = open(os.path.join(config_dir, f"uav_api_{i + 1}.log"), "w")
        proc = subprocess.Popen(
            ["uav-api", "--config", config_path],
            stdout=log_file,
            stderr=log_file,
        )
        uav_api_processes.append(proc)
        time.sleep(2)  # Stagger launches to avoid port conflicts


def wait_for_apis():
    """Wait for all 6 APIs to be healthy by polling /telemetry/gps."""
    print("Waiting for all UAV APIs to become healthy...")
    for i in range(1, NUM_DRONES + 1):
        url = f"http://localhost:{8000 + i}/telemetry/gps_raw"
        retries = 0
        max_retries = 120
        while retries < max_retries:
            try:
                resp = requests.get(url, timeout=2)
                if resp.status_code == 200:
                    resp_json = resp.json()
                    if resp_json["info"]["satelites"] > 0:
                        print(f"  UAV {i} (port {8000 + i}) is ready.")
                        break
            except requests.ConnectionError:
                pass
            retries += 1
            time.sleep(2)
        else:
            print(f"ERROR: UAV {i} (port {8000 + i}) did not become healthy after {max_retries * 2}s")
            cleanup()
            sys.exit(1)

    print("All UAV APIs are healthy.")


def launch_formation_scripts(radius, orientation):
    """Launch 5 formation_polygon.py instances as background processes."""
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "formation_polygon.py")

    for drone_id in range(1, NUM_FOLLOWERS + 1):
        print(f"Launching formation script for drone {drone_id}...")
        proc = subprocess.Popen(
            [
                sys.executable, script_path,
                "--drone_id", str(drone_id),
                "--n", str(NUM_FOLLOWERS),
                "--master_url", MASTER_URL,
                "--base_port", "8000",
                "--radius", str(radius),
                "--orientation", orientation,
            ],
        )
        formation_processes.append(proc)
        time.sleep(1)


def euclidean_distance(p1, p2):
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2 + (p1[2] - p2[2])**2)


def wait_for_point(point, max_error=3, timeout=120):
    """Poll master's NED position until it reaches the target point."""
    start = time.time()
    while time.time() < start + timeout:
        try:
            ned_result = requests.get(f"{MASTER_URL}/telemetry/ned", timeout=2)
            if ned_result.status_code == 200:
                ned_pos = ned_result.json()["info"]["position"]
                current = (ned_pos["x"], ned_pos["y"], ned_pos["z"])
                distance = euclidean_distance(point, current)
                if distance < max_error:
                    return True
        except requests.ConnectionError:
            pass
        time.sleep(0.5)
    return False


def fly_master_square(square_size):
    """Arm, takeoff, and fly the master drone in a square path using non-blocking NED."""
    alt = -TAKEOFF_ALT  # NED: negative z = up
    half = square_size / 2

    # Arm
    print("[Master] Arming...")
    arm_result = requests.get(f"{MASTER_URL}/command/arm")
    if arm_result.status_code != 200:
        print(f"[Master] ERROR: Arm failed. Code: {arm_result.status_code}")
        return

    # Takeoff
    print(f"[Master] Taking off to {TAKEOFF_ALT}m...")
    takeoff_result = requests.get(f"{MASTER_URL}/command/takeoff", params={"alt": TAKEOFF_ALT})
    if takeoff_result.status_code != 200:
        print(f"[Master] ERROR: Takeoff failed. Code: {takeoff_result.status_code}")
        return

    # Wait a bit for stable hover
    time.sleep(5)

    square_points = [
        (half, half, alt),
        (half, -half, alt),
        (-half, -half, alt),
        (-half, half, alt),
    ]

    print("[Master] Starting square path...")
    lap = 1
    while True:
        print(f"[Master] --- Lap {lap} ---")
        for i, point in enumerate(square_points):
            point_data = {"x": point[0], "y": point[1], "z": point[2]}
            result = requests.post(f"{MASTER_URL}/movement/go_to_ned", json=point_data)
            if result.status_code != 200:
                print(f"[Master] ERROR: Movement failed. Code: {result.status_code}")
                return

            print(f"[Master] Heading to corner {i + 1}: ({point[0]}, {point[1]}, {point[2]})")
            arrived = wait_for_point(point, max_error=3, timeout=120)
            if not arrived:
                print(f"[Master] WARNING: Timeout reaching corner {i + 1}")
            else:
                print(f"[Master] Reached corner {i + 1}")

        lap += 1


def cleanup():
    """Terminate all subprocesses."""
    print("\n--- CLEANUP ---")

    # Terminate formation scripts (they handle their own RTL via KeyboardInterrupt)
    for proc in formation_processes:
        if proc.poll() is None:
            proc.send_signal(signal.SIGINT)
    # Give them time to send RTL
    time.sleep(3)
    for proc in formation_processes:
        if proc.poll() is None:
            proc.terminate()

    # Terminate uav-api instances
    for proc in uav_api_processes:
        if proc.poll() is None:
            proc.terminate()
    # Wait for them to exit
    for proc in uav_api_processes:
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    # Clean up temp config files
    if config_dir and os.path.exists(config_dir):
        import shutil
        shutil.rmtree(config_dir, ignore_errors=True)

    print("Cleanup complete.")


# --- MAIN ---
if __name__ == "__main__":
    args = parse_args()

    try:
        # Phase 1: Generate configs and launch APIs
        configs = generate_configs(args.ardupilot_path, args.speedup)
        launch_uav_apis(configs)
        wait_for_apis()

        # Phase 2: Launch formation followers
        launch_formation_scripts(args.radius, args.orientation)

        # Phase 3: Fly master in a square (blocks until Ctrl+C)
        fly_master_square(args.square_size)

    except KeyboardInterrupt:
        print("\n--- INTERRUPT DETECTED ---")
    except Exception as e:
        print(f"\n--- ERROR: {e} ---")
    finally:
        cleanup()
