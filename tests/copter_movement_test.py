"""
Integration tests for the movement router.

Own SITL instance (port 8003, sysid 3), armed and hovering at 15 m.

Movement tests displace the drone, so assertions are on DELTAS from the
position captured at the start of each test, never on absolute coordinates.
Tests halt the drone with a zero-velocity setpoint before finishing.
"""

import time

import pytest

from conftest import make_api_fixture

pytestmark = [pytest.mark.sitl, pytest.mark.copter]

api = make_api_fixture(port=8003, sysid=3, flying=True)


# ── helpers ───────────────────────────────────────────────────────────────────

def ned_info(api):
    r = api.get("/telemetry/ned")
    assert r.status_code == 200
    return r.json()["info"]


def general_info(api):
    r = api.get("/telemetry/general")
    assert r.status_code == 200
    return r.json()["info"]


def observe(api, predicate, timeout=6, interval=0.1):
    """Poll NED telemetry until predicate(info) holds; return whether it did.

    Velocity must be caught in the act: a single velocity setpoint expires
    after GUID_TIMEOUT (3 sim-seconds) and short position moves complete in
    under a second of wall time at speedup 5, so a fixed sleep followed by
    one sample lands after the drone has already stopped.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate(ned_info(api)):
            return True
        time.sleep(interval)
    return False


def halt(api):
    """Zero-velocity setpoint: reliably stops the drone in GUIDED."""
    r = api.post("/movement/travel_at_ned", json={"vx": 0.0, "vy": 0.0, "vz": 0.0})
    assert r.status_code == 200
    time.sleep(1)


# ── tests ─────────────────────────────────────────────────────────────────────

class TestTravelAtNed:
    def test_basic_velocity(self, api):
        """POST /movement/travel_at_ned → drone moves north."""
        r = api.post("/movement/travel_at_ned", json={"vx": 2.0, "vy": 0.0, "vz": 0.0})
        assert r.status_code == 200

        moved = observe(api, lambda info: info["velocity"]["vx"] > 0.5)
        assert moved, "Never observed vx > 0.5 after travel_at_ned"

        halt(api)

    def test_with_look_at_target(self, api):
        """POST /movement/travel_at_ned with look_at_target=True."""
        r = api.post("/movement/travel_at_ned", json={
            "vx": 2.0, "vy": 0.0, "vz": 0.0, "look_at_target": True
        })
        assert r.status_code == 200

        moved = observe(api, lambda info: info["velocity"]["vx"] > 0.5)
        assert moved, "Never observed vx > 0.5 after travel_at_ned"

        halt(api)


class TestGoToNed:
    def test_default_look_at(self, api):
        """POST /movement/go_to_ned → drone starts moving toward target."""
        start_x = ned_info(api)["position"]["x"]

        r = api.post("/movement/go_to_ned", json={
            "x": start_x + 10.0, "y": 0.0, "z": -15.0
        })
        assert r.status_code == 200

        time.sleep(2)

        x = ned_info(api)["position"]["x"]
        assert x - start_x > 0.5, (
            f"Expected drone to move north, delta={x - start_x}"
        )

        # Brake mid-move, then return to GUIDED so later tests can move
        r = api.get("/command/brake")
        assert r.status_code == 200
        stopped = observe(
            api,
            lambda info: (info["velocity"]["vx"] ** 2 + info["velocity"]["vy"] ** 2) ** 0.5 < 0.3,
        )
        assert stopped, "Drone did not halt after /command/brake"

        r = api.get("/command/guided")
        assert r.status_code == 200

    def test_with_look_at_target(self, api):
        """POST /movement/go_to_ned with look_at_target=True."""
        start_x = ned_info(api)["position"]["x"]

        r = api.post("/movement/go_to_ned", json={
            "x": start_x + 20.0, "y": 0.0, "z": -15.0, "look_at_target": True
        })
        assert r.status_code == 200
        body = r.json()
        assert "result" in body

        halt(api)


class TestDrive:
    def test_drive_with_telemetry(self, api):
        """POST /movement/drive → drone moves relative to current position."""
        r = api.post("/movement/drive", json={"x": 15.0, "y": 0.0, "z": 0.0})
        assert r.status_code == 200

        moved = observe(
            api,
            lambda info: (info["velocity"]["vx"] ** 2 + info["velocity"]["vy"] ** 2) ** 0.5 > 0.3,
        )
        assert moved, "Never observed movement after drive"

        halt(api)


class TestDriveBody:
    def test_drive_body_moves(self, api):
        """POST /movement/drive_body → drone moves relative to its heading."""
        r = api.post("/movement/drive_body", json={"front": 15.0, "right": 0.0, "down": 0.0})
        assert r.status_code == 200

        moved = observe(
            api,
            lambda info: (info["velocity"]["vx"] ** 2 + info["velocity"]["vy"] ** 2) ** 0.5 > 0.3,
        )
        assert moved, "Never observed movement after drive_body"

        halt(api)

    def test_drive_body_wait_follows_heading(self, api):
        """POST /movement/drive_body_wait with heading 45° → the front offset
        splits equally between north and east (8·cos45° ≈ 8·sin45° ≈ 5.66 m).

        A plain offset-NED implementation would move all-north and an
        axis-swapped one all-east, so neither can pass this.
        """
        r = api.get("/movement/set_heading", params={"heading": 45})
        assert r.status_code == 200
        turned = observe(
            api, lambda _info: abs(general_info(api)["heading"] - 45) <= 5, timeout=15
        )
        assert turned, "Drone never reached heading 45"

        start = ned_info(api)["position"]
        r = api.post("/movement/drive_body_wait", json={"front": 8.0, "right": 0.0, "down": 0.0})
        assert r.status_code == 200

        pos = ned_info(api)["position"]
        expected = 8.0 * (2 ** 0.5) / 2  # ≈ 5.66 m on each horizontal axis
        assert abs((pos["x"] - start["x"]) - expected) < 2.0, (
            f"north delta {pos['x'] - start['x']}, expected ~{expected}"
        )
        assert abs((pos["y"] - start["y"]) - expected) < 2.0, (
            f"east delta {pos['y'] - start['y']}, expected ~{expected}"
        )

        halt(api)


class TestGoToGps:
    def test_with_look_at_target(self, api):
        """POST /movement/go_to_gps with look_at_target=True."""
        r = api.get("/telemetry/gps")
        assert r.status_code == 200
        gps = r.json()["info"]["position"]

        # Offset lat slightly north (~11m per 0.0001 degrees)
        r = api.post("/movement/go_to_gps/", json={
            "lat": gps["lat"] + 0.0002,
            "long": gps["lon"],
            "alt": gps["relative_alt"],
            "look_at_target": True,
        })
        assert r.status_code == 200

        halt(api)
