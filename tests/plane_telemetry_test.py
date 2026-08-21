"""
Integration tests for the plane telemetry router (/telemetry/...).

Own SITL instance (port 8009, sysid 9, ArduPlane), grounded — telemetry
needs no flight.
"""

import time

import pytest

from conftest import make_api_fixture

pytestmark = [pytest.mark.sitl, pytest.mark.plane]

api = make_api_fixture(port=8009, sysid=9, vehicle="plane")


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
