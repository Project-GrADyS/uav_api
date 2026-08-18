"""
Shared fixtures and helpers for integration tests.

Each test module gets its OWN SITL-backed API server (module-scoped fixture,
built with make_api_fixture) on a unique port/sysid, so state can't leak
between modules and destructive tests (land, RTL, set_home) can't poison
other files. Modules must run sequentially: every SITL instance shares the
same working directory (~/uav_api_logs/ardupilot_logs).

Port/sysid allocation:
    copter_command_test    8001 / 1
    mission_test           8002 / 2
    copter_movement_test   8003 / 3
    peripherical_test      8004 / 4
    copter_telemetry_test  8005 / 5
    concurrency_test       8006 / 6
    plane_command_test     8007 / 7
    plane_movement_test    8008 / 8
    plane_telemetry_test   8009 / 9

All modules in this directory spawn SITL and are marked with the `sitl`
marker, plus `copter` or `plane` for their vehicle (mission, peripherical
and concurrency run on a copter app and carry the copter marker). The unit
layer in tests/unit/ runs anywhere with `pytest -m "not sitl"`.

Requirements:
    - ArduPilot installed with sim_vehicle.py on PATH (or pass --ardupilot_path)
    - pytest, requests, psutil

SITL runs with --headless, so no X server or xterm is needed. SITL output
goes to ~/uav_api_logs/ardupilot_logs/sitl_<sysid>.log if you need to see
why it failed; the API log is ~/uav_api_logs/uav_logs/uav_<sysid>.log.
"""

import os
import time
import psutil
import pytest
import requests

from uav_api.run_api import spawn_with_args

SPEEDUP = 5
ARDUPILOT_LOGS = os.path.expanduser("~/uav_api_logs/ardupilot_logs")


# ── HTTP client ───────────────────────────────────────────────────────────────

class Client:
    """HTTP helpers bound to one API instance.

    Blocking endpoints (arm, takeoff, land, rtl, *_wait) must pass a timeout
    LARGER than the endpoint's internal timeout: if the client gives up first,
    the abandoned handler keeps running and races every later request on the
    shared MAVLink link.
    """

    def __init__(self, port):
        self.base_url = f"http://localhost:{port}"

    def get(self, path, timeout=10, **kwargs):
        return requests.get(f"{self.base_url}{path}", timeout=timeout, **kwargs)

    def post(self, path, json=None, timeout=10, **kwargs):
        return requests.post(f"{self.base_url}{path}", json=json, timeout=timeout, **kwargs)

    def delete(self, path, timeout=10, **kwargs):
        return requests.delete(f"{self.base_url}{path}", timeout=timeout, **kwargs)


# ── wait helpers ──────────────────────────────────────────────────────────────

def wait_for_api(client, proc, timeout=90):
    """Poll /telemetry/general until the server is up; fail fast if it died."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not proc.is_alive():
            raise RuntimeError(
                "API server process died during startup — see "
                "~/uav_api_logs/uav_logs and ~/uav_api_logs/ardupilot_logs"
            )
        try:
            r = client.get("/telemetry/general")
            if r.status_code == 200:
                return
        except requests.ConnectionError:
            pass
        time.sleep(2)
    raise TimeoutError("API did not become ready within timeout")


def wait_for_altitude(client, target_alt, tolerance=2, timeout=60):
    """Wait until NED altitude (negative-down) stabilises near target."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get("/telemetry/ned")
        if r.status_code == 200:
            z = r.json()["info"]["position"]["z"]
            if abs(z - (-target_alt)) < tolerance:
                return
        time.sleep(1)
    raise TimeoutError(f"Altitude did not reach {target_alt}m within {timeout}s")


def wait_for_relative_alt(client, min_alt, timeout=60):
    """Wait until GPS relative altitude reaches min_alt (plane has no /telemetry/ned)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get("/telemetry/gps")
        if r.status_code == 200:
            if r.json()["info"]["position"]["relative_alt"] >= min_alt:
                return
        time.sleep(1)
    raise TimeoutError(f"Relative altitude did not reach {min_alt}m within {timeout}s")


# ── SITL/API lifecycle ────────────────────────────────────────────────────────

def _kill_stray_sitl(sysid):
    """Kill SITL processes left over by a SIGKILLed server (lifespan teardown
    never ran, so they survive holding the SITL TCP ports)."""
    tag = f"SITL_ID_{sysid}"
    for proc in psutil.process_iter(["environ"]):
        try:
            env = proc.info["environ"]
            if env and env.get("UAV_SITL_TAG") == tag:
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue


def start_api(port, sysid, flying=False, vehicle="copter"):
    _kill_stray_sitl(sysid)
    # Parameters written by a previous run (e.g. SIM_SPEEDUP) persist in the
    # shared eeprom and silently override the --speedup we pass.
    eeprom = os.path.join(ARDUPILOT_LOGS, "eeprom.bin")
    if os.path.exists(eeprom):
        os.remove(eeprom)

    proc = spawn_with_args([
        "--simulated", "true",
        "--headless",
        "--speedup", str(SPEEDUP),
        "--port", str(port),
        "--sysid", str(sysid),
        "--uav_connection", f"127.0.0.1:{17170 + sysid}",
        "--vehicle", vehicle,
    ])
    client = Client(port)
    try:
        wait_for_api(client, proc)
        if flying and vehicle == "plane":
            # Fixed-wing: hovering is impossible; "flying" means airborne at
            # cruise altitude in GUIDED. Client timeouts exceed the endpoints'
            # internal ones (arm 120, takeoff 120).
            r = client.get("/command/arm", timeout=150)
            assert r.status_code == 200, f"Arm failed: {r.text}"
            r = client.get("/command/takeoff", params={"alt": 50}, timeout=180)
            assert r.status_code == 200, f"Takeoff failed: {r.text}"
            wait_for_relative_alt(client, 35)
        elif flying:
            r = client.get("/command/arm", timeout=60)
            assert r.status_code == 200, f"Arm failed: {r.text}"
            r = client.get("/command/takeoff", params={"alt": 15}, timeout=60)
            assert r.status_code == 200, f"Takeoff failed: {r.text}"
            wait_for_altitude(client, 15, tolerance=3)
        return proc, client
    except BaseException:
        stop_api(proc, sysid)
        raise


def stop_api(proc, sysid):
    proc.terminate()
    proc.join(timeout=30)
    if proc.is_alive():
        proc.kill()
        proc.join(timeout=5)
        # SIGKILL skipped the lifespan teardown; reap its SITL ourselves.
        _kill_stray_sitl(sysid)


def make_api_fixture(port, sysid, flying=False, vehicle="copter"):
    """Build a module-scoped fixture that yields a Client for a fresh
    SITL-backed API server. flying=True arms and takes off first (copter
    hovers at 15 m; plane climbs to 50 m and cruises in GUIDED)."""

    @pytest.fixture(scope="module")
    def api(request):
        proc, client = start_api(port, sysid, flying, vehicle)
        yield client
        stop_api(proc, sysid)

    return api
