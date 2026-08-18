"""
Integration tests for the plane routers (--vehicle plane).

Own SITL instance (port 8007, sysid 7, ArduPlane), started GROUNDED.

Fixed-wing dynamics dictate the test order: a plane cannot hover, so once
airborne every test must leave it airborne, and it is never disarmed mid-air.
Grounded tests (telemetry, set_home) run first, then a single flight arc:
arm → takeoff → go_to_gps_wait (out) → go_to_gps (back, fire-and-forget) →
stop (LOITER) → rtl (loiters at home; plane RTL does not land) → land_at
(fire-and-forget mission landing — touchdown is deliberately NOT awaited,
fixed-wing SITL landings are too flaky to gate the suite on).

Client timeouts are strictly larger than each endpoint's internal timeout
(arm 120, takeoff 120, go_to_gps_wait 180, rtl 250 — see Client docstring
in conftest).
"""

import time

import pytest

from conftest import make_api_fixture

pytestmark = pytest.mark.sitl

api = make_api_fixture(port=8007, sysid=7, vehicle="plane")

# ~400 m north (1 deg lat ~= 111 km) — far enough that arrival (50 m
# accuracy) proves real movement, short enough to fly quickly at speedup 5.
DELTA_LAT = 400 / 111_000
CRUISE_ALT = 50


def gps_info(api):
    r = api.get("/telemetry/gps")
    assert r.status_code == 200, r.text
    return r.json()["info"]


class TestGroundedTelemetry:

    def test_general(self, api):
        r = api.get("/telemetry/general")
        assert r.status_code == 200
        info = r.json()["info"]
        for key in ("airspeed", "groundspeed", "heading", "throttle", "alt"):
            assert key in info, f"Missing key: {key}"

    def test_gps(self, api):
        info = gps_info(api)
        assert abs(info["position"]["relative_alt"]) < 2, "plane should be on the ground"
        assert -90 <= info["position"]["lat"] <= 90
        assert -180 <= info["position"]["lon"] <= 180

    def test_battery_info(self, api):
        r = api.get("/telemetry/battery_info")
        assert r.status_code == 200
        assert "info" in r.json()

    def test_sensor_status(self, api):
        r = api.get("/telemetry/sensor_status")
        assert r.status_code == 200
        assert "status" in r.json()

    def test_error_info(self, api):
        r = api.get("/telemetry/error_info")
        assert r.status_code == 200
        assert "info" in r.json()

    def test_home_info(self, api):
        # HOME_POSITION only exists once the EKF sets its origin (GPS lock),
        # which can lag the API becoming responsive — poll until it appears.
        deadline = time.time() + 90
        while True:
            r = api.get("/telemetry/home_info")
            if r.status_code == 200:
                break
            assert time.time() < deadline, f"home never became available: {r.text}"
            time.sleep(2)
        body = r.json()
        for key in ("lat", "lon", "altitude", "x", "y", "z"):
            assert key in body, f"Missing key: {key}"


class TestFlight:
    """One continuous flight arc — tests depend on running in order."""

    def test_set_home_while_grounded(self, api):
        r = api.get("/command/set_home", timeout=60)
        assert r.status_code == 200, r.text

    def test_arm(self, api):
        r = api.get("/command/arm", timeout=150)
        assert r.status_code == 200, r.text
        assert r.json()["result"] == "Armed vehicle"

    def test_takeoff(self, api):
        r = api.get("/command/takeoff", params={"alt": CRUISE_ALT}, timeout=180)
        assert r.status_code == 200, r.text
        relative_alt = gps_info(api)["position"]["relative_alt"]
        assert relative_alt > CRUISE_ALT * 0.7, (
            f"takeoff returned but plane is at {relative_alt}m"
        )

    def test_go_to_gps_wait(self, api):
        start = gps_info(api)["position"]
        target = {
            "lat": start["lat"] + DELTA_LAT,
            "long": start["lon"],
            "alt": CRUISE_ALT,
        }
        r = api.post("/movement/go_to_gps_wait", json=target, timeout=240)
        assert r.status_code == 200, r.text
        # go_to_gps_wait's arrival accuracy is 50 m; assert the plane actually
        # covered most of the distance north.
        moved = (gps_info(api)["position"]["lat"] - start["lat"]) / DELTA_LAT
        assert moved > 0.5, f"plane only covered {moved:.0%} of the leg"

    def test_go_to_gps_fire_and_forget(self, api):
        home = api.get("/telemetry/home_info").json()
        r = api.post("/movement/go_to_gps", json={
            "lat": home["lat"],
            "long": home["lon"],
            "alt": CRUISE_ALT,
        })
        assert r.status_code == 200, r.text

    def test_stop_loiters(self, api):
        r = api.get("/movement/stop")
        assert r.status_code == 200, r.text
        # A loitering plane stays airborne and near where it was stopped:
        # two spaced reads must stay within a loiter-circle-sized bound
        # (WP_LOITER_RAD defaults to ~60 m; allow drift while it settles).
        first = gps_info(api)["position"]
        time.sleep(3)
        second = gps_info(api)["position"]
        assert second["relative_alt"] > 10, "plane should still be airborne"
        lat_drift_m = abs(second["lat"] - first["lat"]) * 111_000
        assert lat_drift_m < 400, f"plane drifted {lat_drift_m:.0f}m while loitering"

    def test_rtl(self, api):
        home = api.get("/telemetry/home_info").json()
        r = api.get("/command/rtl", timeout=310)
        assert r.status_code == 200, r.text
        # do_RTL returns once within 120 m of home (plane loiters, no landing)
        pos = gps_info(api)["position"]
        lat_dist_m = abs(pos["lat"] - home["lat"]) * 111_000
        assert lat_dist_m < 400, f"plane is {lat_dist_m:.0f}m from home after RTL"

    def test_land_at_starts_landing_mission(self, api):
        home = api.get("/telemetry/home_info").json()
        r = api.get("/command/land_at", params={
            "lat": home["lat"],
            "long": home["lon"],
        }, timeout=60)
        assert r.status_code == 200, r.text
        # Fire-and-forget: the endpoint returns once the AUTO mode switch
        # succeeds. Touchdown is not awaited (see module docstring).
