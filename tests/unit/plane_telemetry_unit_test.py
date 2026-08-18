"""Unit tests for the plane telemetry router.

Pins the MAVLink-unit conversions exactly, like the copter counterpart.
"""

import pytest

from unit_helpers import BATTERY, ERRORS, GENERAL, SENSORS

pytestmark = pytest.mark.plane


class TestTelemetry:
    def test_general(self, plane_client):
        r = plane_client.get("/telemetry/general")
        assert r.status_code == 200
        assert r.json()["info"] == {
            "airspeed": GENERAL.airspeed,
            "groundspeed": GENERAL.groundspeed,
            "heading": GENERAL.heading,
            "throttle": GENERAL.throttle,
            "alt": GENERAL.alt,
        }

    def test_gps_conversions(self, plane_client):
        r = plane_client.get("/telemetry/gps")
        assert r.status_code == 200
        info = r.json()["info"]
        assert info["position"] == {
            "lat": -15.840081,
            "lon": -47.926642,
            "alt": 1042.0,
            "relative_alt": 15.0,
        }
        assert info["velocity"] == {"vx": 1.2, "vy": -0.4, "vz": 0.1}
        assert info["heading"] == 90.0

    def test_battery_info(self, plane_client):
        r = plane_client.get("/telemetry/battery_info")
        assert r.status_code == 200
        assert r.json()["info"] == BATTERY

    def test_sensor_status(self, plane_client):
        r = plane_client.get("/telemetry/sensor_status")
        assert r.status_code == 200
        assert r.json()["status"] == SENSORS

    def test_error_info(self, plane_client):
        r = plane_client.get("/telemetry/error_info")
        assert r.status_code == 200
        assert r.json()["info"] == ERRORS

    def test_home_info_conversions(self, plane_client):
        r = plane_client.get("/telemetry/home_info")
        assert r.status_code == 200
        body = r.json()
        assert body["lat"] == -15.840081
        assert body["lon"] == -47.926642
        assert body["altitude"] == 1042.0

    def test_telemetry_failure_is_500(self, plane_client, fake_plane):
        fake_plane.get_gps_info.side_effect = Exception("no heartbeat")
        r = plane_client.get("/telemetry/gps")
        assert r.status_code == 500
        assert "GET_GPS_POSITION FAIL" in r.json()["detail"]
