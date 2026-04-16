"""
Integration tests for the command router (/command/...).

Uses the session-scoped SITL server from conftest.py, which starts
already armed and hovering at 15 m altitude.
"""

import time

from conftest import get, wait_for_altitude


# ── Speed-setting endpoints (non-destructive) ───────────────────────────────


class TestSetSpeeds:

    def test_set_air_speed(self, api_server):
        r = get("/command/set_air_speed", params={"new_v": 10})
        assert r.status_code == 200
        body = r.json()
        assert "device" in body
        assert "id" in body
        assert "result" in body
        assert "10" in body["result"]

    def test_set_ground_speed(self, api_server):
        r = get("/command/set_ground_speed", params={"new_v": 8})
        assert r.status_code == 200
        body = r.json()
        assert "device" in body
        assert "id" in body
        assert "result" in body
        assert "8" in body["result"]

    def test_set_climb_speed(self, api_server):
        r = get("/command/set_climb_speed", params={"new_v": 3})
        assert r.status_code == 200
        body = r.json()
        assert "device" in body
        assert "id" in body
        assert "result" in body
        assert "3" in body["result"]

    def test_set_descent_speed(self, api_server):
        r = get("/command/set_descent_speed", params={"new_v": 2})
        assert r.status_code == 200
        body = r.json()
        assert "device" in body
        assert "id" in body
        assert "result" in body
        assert "2" in body["result"]


# ── Sim speedup ──────────────────────────────────────────────────────────────


class TestSetSimSpeedup:

    def test_set_sim_speedup(self, api_server):
        r = get("/command/set_sim_speedup", params={"sim_factor": 5})
        assert r.status_code == 200
        body = r.json()
        assert "device" in body
        assert "id" in body
        assert "result" in body
        assert "5" in body["result"]

        r = get("/command/set_sim_speedup", params={"sim_factor": 1})
        assert r.status_code == 200
        body = r.json()
        assert "device" in body
        assert "id" in body
        assert "result" in body
        assert "1" in body["result"]

# ── Set home ─────────────────────────────────────────────────────────────────


class TestSetHome:

    def test_set_home(self, api_server):
        r = get("/command/set_home")
        assert r.status_code == 200
        body = r.json()
        assert "device" in body
        assert "id" in body
        assert "result" in body
        assert "success" in body["result"].lower()


# ── Land then re-arm ────────────────────────────────────────────────────────


class TestLandAndRearm:

    def test_land_and_rearm(self, api_server):
        # Land
        r = get("/command/land")
        assert r.status_code == 200
        body = r.json()
        assert "device" in body
        assert "id" in body
        assert "result" in body

        # Wait for the drone to touch down
        time.sleep(10)

        # Re-arm
        r = get("/command/arm")
        assert r.status_code == 200
        body = r.json()
        assert "device" in body
        assert "id" in body
        assert "result" in body

        # Takeoff back to 15 m
        r = get("/command/takeoff", params={"alt": 15})
        assert r.status_code == 200
        body = r.json()
        assert "device" in body
        assert "id" in body
        assert "result" in body

        # Restore hover state for subsequent tests
        wait_for_altitude(15, tolerance=3, timeout=40)


# ── RTL then re-arm ─────────────────────────────────────────────────────────


class TestRtl:

    def test_rtl_and_rearm(self, api_server):
        # RTL
        r = get("/command/rtl")
        assert r.status_code == 200
        body = r.json()
        assert "device" in body
        assert "id" in body
        assert "result" in body

        # Wait for RTL to complete
        time.sleep(15)

        # Re-arm
        r = get("/command/arm")
        assert r.status_code == 200
        body = r.json()
        assert "device" in body
        assert "id" in body
        assert "result" in body

        # Takeoff back to 15 m
        r = get("/command/takeoff", params={"alt": 15})
        assert r.status_code == 200
        body = r.json()
        assert "device" in body
        assert "id" in body
        assert "result" in body

        # Restore hover state for subsequent tests
        wait_for_altitude(15, tolerance=3, timeout=40)
