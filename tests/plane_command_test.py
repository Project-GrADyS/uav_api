"""
Integration tests for the plane command router (/command/...).

Own SITL instance (port 8007, sysid 7, ArduPlane), started GROUNDED.

Fixed-wing dynamics dictate the test order: a plane cannot hover, so once
airborne every test must leave it airborne, and it is never disarmed mid-air.
One continuous flight arc: set_home (grounded) → arm → takeoff → rtl (loiters
at home; plane RTL does not land) → land_at (fire-and-forget mission landing —
touchdown is deliberately NOT awaited, fixed-wing SITL landings are too flaky
to gate the suite on).

Client timeouts are strictly larger than each endpoint's internal timeout
(arm 120, takeoff 120, rtl 250 — see Client docstring in conftest).
"""

import pytest

from conftest import make_api_fixture

pytestmark = [pytest.mark.sitl, pytest.mark.plane]

api = make_api_fixture(port=8007, sysid=7, vehicle="plane")

CRUISE_ALT = 50


def gps_info(api):
    r = api.get("/telemetry/gps")
    assert r.status_code == 200, r.text
    return r.json()["info"]


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
