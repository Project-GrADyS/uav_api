"""
Integration tests for the movement router.

Uses the shared SITL session from conftest.py (session-scoped).

Run:
    pytest tests/movement_test.py -v -s --timeout=120
"""

import time

from conftest import get, post


# ── tests (run in order, share the same SITL session) ────────────────────────

class TestTravelAtNed:
    def test_basic_velocity(self, api_server):
        """POST /movement/travel_at_ned → drone moves north."""
        r = post("/movement/travel_at_ned", json={"x": 2.0, "y": 0.0, "z": 0.0})
        assert r.status_code == 200

        time.sleep(2)

        r = get("/telemetry/ned")
        assert r.status_code == 200
        vx = r.json()["info"]["velocity"]["vx"]
        assert vx > 0.5, f"Expected positive vx, got {vx}"

        r = get("/movement/stop")
        assert r.status_code == 200

    def test_with_look_at_target(self, api_server):
        """POST /movement/travel_at_ned with look_at_target=True."""
        r = post("/movement/travel_at_ned", json={
            "x": 2.0, "y": 0.0, "z": 0.0, "look_at_target": True
        })
        assert r.status_code == 200

        time.sleep(2)

        r = get("/telemetry/ned")
        assert r.status_code == 200
        vx = r.json()["info"]["velocity"]["vx"]
        assert vx > 0.5, f"Expected positive vx, got {vx}"

        r = get("/movement/stop")
        assert r.status_code == 200


class TestGoToNed:
    def test_default_look_at(self, api_server):
        """POST /movement/go_to_ned → drone starts moving toward target."""
        r = post("/movement/go_to_ned", json={"x": 10.0, "y": 0.0, "z": -15.0})
        assert r.status_code == 200

        time.sleep(2)

        r = get("/telemetry/ned")
        assert r.status_code == 200
        pos = r.json()["info"]["position"]
        # Drone should have started moving north (x > 0)
        assert pos["x"] > 0.5, f"Expected drone to move north, x={pos['x']}"

        r = get("/movement/stop")
        assert r.status_code == 200

    def test_with_look_at_target(self, api_server):
        """POST /movement/go_to_ned with look_at_target=True."""
        r = post("/movement/go_to_ned", json={
            "x": 20.0, "y": 0.0, "z": -15.0, "look_at_target": True
        })
        assert r.status_code == 200
        body = r.json()
        assert "result" in body

        r = get("/movement/stop")
        assert r.status_code == 200


class TestDrive:
    def test_drive_with_telemetry(self, api_server):
        """POST /movement/drive → drone moves relative to current position."""
        r = post("/movement/drive", json={"x": 5.0, "y": 0.0, "z": 0.0})
        assert r.status_code == 200

        time.sleep(2)

        r = get("/telemetry/ned")
        assert r.status_code == 200
        vel = r.json()["info"]["velocity"]
        # Should be moving (some non-trivial velocity)
        speed = (vel["vx"] ** 2 + vel["vy"] ** 2) ** 0.5
        assert speed > 0.3, f"Expected movement, speed={speed}"

        r = get("/movement/stop")
        assert r.status_code == 200


class TestGoToGps:
    def test_with_look_at_target(self, api_server):
        """POST /movement/go_to_gps with look_at_target=True."""
        # Get current GPS position
        r = get("/telemetry/gps")
        assert r.status_code == 200
        gps = r.json()["info"]["position"]

        # Offset lat slightly north (~11m per 0.0001 degrees)
        r = post("/movement/go_to_gps/", json={
            "lat": gps["lat"] + 0.0002,
            "long": gps["lon"],
            "alt": gps["relative_alt"],
            "look_at_target": True,
        })
        assert r.status_code == 200

        r = get("/movement/stop")
        assert r.status_code == 200
