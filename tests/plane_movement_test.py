"""
Integration tests for the plane movement router (/movement/...).

Own SITL instance (port 8008, sysid 8, ArduPlane), started FLYING: the
fixture arms and takes off to 50 m in GUIDED (see conftest start_api).

Order matters — the plane stays airborne throughout: go_to_gps_wait (out) →
go_to_gps back toward home (fire-and-forget) → stop (LOITER).
"""

import time

import pytest

from conftest import make_api_fixture

pytestmark = [pytest.mark.sitl, pytest.mark.plane]

api = make_api_fixture(port=8008, sysid=8, vehicle="plane", flying=True)

# ~400 m north (1 deg lat ~= 111 km) — far enough that arrival (120 m
# accuracy) proves real movement, short enough to fly quickly at speedup 5.
DELTA_LAT = 400 / 111_000
CRUISE_ALT = 50


def gps_info(api):
    r = api.get("/telemetry/gps")
    assert r.status_code == 200, r.text
    return r.json()["info"]


class TestMovement:
    """One continuous flight — tests depend on running in order."""

    def test_go_to_gps_wait(self, api):
        start = gps_info(api)["position"]
        target = {
            "lat": start["lat"] + DELTA_LAT,
            "long": start["lon"],
            "alt": CRUISE_ALT,
        }
        r = api.post("/movement/go_to_gps_wait", json=target, timeout=240)
        assert r.status_code == 200, r.text
        # go_to_gps_wait's arrival accuracy is 2x the loiter radius; assert
        # the plane actually covered most of the distance north.
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
