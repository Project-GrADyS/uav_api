"""
Integration tests for the command router (/command/...).

Own SITL instance (port 8001, sysid 1), started GROUNDED: the parameter and
home tests must run before any flight (set_home while airborne shifts every
later relative altitude), and the flight tests arm/take off themselves.
"""

import time

from conftest import make_api_fixture, wait_for_altitude, SPEEDUP

api = make_api_fixture(port=8001, sysid=1, flying=False)


# ── Speed-setting endpoints (non-destructive) ───────────────────────────────


class TestSetSpeeds:

    def test_set_air_speed(self, api):
        r = api.get("/command/set_air_speed", params={"new_v": 10})
        assert r.status_code == 200
        body = r.json()
        assert "device" in body
        assert "id" in body
        assert "result" in body
        assert "10" in body["result"]

    def test_set_ground_speed(self, api):
        r = api.get("/command/set_ground_speed", params={"new_v": 8})
        assert r.status_code == 200
        body = r.json()
        assert "device" in body
        assert "id" in body
        assert "result" in body
        assert "8" in body["result"]

    def test_set_climb_speed(self, api):
        r = api.get("/command/set_climb_speed", params={"new_v": 3})
        assert r.status_code == 200
        body = r.json()
        assert "device" in body
        assert "id" in body
        assert "result" in body
        assert "3" in body["result"]

    def test_set_descent_speed(self, api):
        r = api.get("/command/set_descent_speed", params={"new_v": 2})
        assert r.status_code == 200
        body = r.json()
        assert "device" in body
        assert "id" in body
        assert "result" in body
        assert "2" in body["result"]


# ── Sim speedup ──────────────────────────────────────────────────────────────


class TestSetSimSpeedup:

    def test_set_sim_speedup(self, api):
        r = api.get("/command/set_sim_speedup", params={"sim_factor": 1})
        assert r.status_code == 200
        body = r.json()
        assert "device" in body
        assert "id" in body
        assert "result" in body
        assert "1" in body["result"]

        # Restore the speedup the fixture launched with — SIM_SPEEDUP is a
        # live parameter and leaving it at 1 slows every later test 5x.
        r = api.get("/command/set_sim_speedup", params={"sim_factor": SPEEDUP})
        assert r.status_code == 200
        body = r.json()
        assert "device" in body
        assert "id" in body
        assert "result" in body
        assert str(SPEEDUP) in body["result"]


# ── Set home (must run on the ground) ────────────────────────────────────────


class TestSetHome:

    def test_set_home(self, api):
        r = api.get("/command/set_home")
        assert r.status_code == 200
        body = r.json()
        assert "device" in body
        assert "id" in body
        assert "result" in body
        assert "success" in body["result"].lower()


# ── Flight: land then re-arm ─────────────────────────────────────────────────


class TestLandAndRearm:

    def test_land_and_rearm(self, api):
        # Initial arm + takeoff (this module's SITL starts grounded)
        r = api.get("/command/arm", timeout=60)
        assert r.status_code == 200, f"Arm failed: {r.text}"
        r = api.get("/command/takeoff", params={"alt": 15}, timeout=60)
        assert r.status_code == 200, f"Takeoff failed: {r.text}"
        wait_for_altitude(api, 15, tolerance=3, timeout=60)

        # Land — blocks until landed AND disarmed (internal timeout 60s + 30s)
        r = api.get("/command/land", timeout=120)
        assert r.status_code == 200, f"Land failed: {r.text}"
        body = r.json()
        assert "device" in body
        assert "id" in body
        assert "result" in body

        # Re-arm
        r = api.get("/command/arm", timeout=60)
        assert r.status_code == 200, f"Re-arm failed: {r.text}"
        body = r.json()
        assert "device" in body
        assert "id" in body
        assert "result" in body

        # Takeoff back to 15 m
        r = api.get("/command/takeoff", params={"alt": 15}, timeout=60)
        assert r.status_code == 200
        body = r.json()
        assert "device" in body
        assert "id" in body
        assert "result" in body

        wait_for_altitude(api, 15, tolerance=3, timeout=60)


# ── Flight: RTL then re-arm ──────────────────────────────────────────────────


class TestRtl:

    def test_rtl_and_rearm(self, api):
        # RTL — blocks until the vehicle is home and disarmed (internal 250s)
        r = api.get("/command/rtl", timeout=300)
        assert r.status_code == 200, f"RTL failed: {r.text}"
        body = r.json()
        assert "device" in body
        assert "id" in body
        assert "result" in body

        # Re-arm
        r = api.get("/command/arm", timeout=60)
        assert r.status_code == 200, f"Re-arm failed: {r.text}"
        body = r.json()
        assert "device" in body
        assert "id" in body
        assert "result" in body

        # Takeoff back to 15 m
        r = api.get("/command/takeoff", params={"alt": 15}, timeout=60)
        assert r.status_code == 200
        body = r.json()
        assert "device" in body
        assert "id" in body
        assert "result" in body

        wait_for_altitude(api, 15, tolerance=3, timeout=60)
