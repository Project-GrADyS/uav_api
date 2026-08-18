"""Unit tests for the plane routers — first coverage of the plane surface.

Everything here (plane command, movement and telemetry) has no SITL test
history; these tests pin the HTTP contract and the router → Plane delegation.
"""

from unit_helpers import BATTERY, ERRORS, GENERAL, SENSORS, assert_envelope

GPS_BODY = {"lat": -15.84, "long": -47.92, "alt": 100}


class TestCommand:
    def test_arm(self, plane_client, fake_plane):
        r = plane_client.get("/command/arm")
        assert r.status_code == 200
        assert_envelope(r.json(), "Armed vehicle")
        fake_plane.change_mode.assert_called_once_with("GUIDED")
        fake_plane.wait_ready_to_arm.assert_called_once_with()
        fake_plane.arm_vehicle.assert_called_once_with()

    def test_arm_failure_is_500(self, plane_client, fake_plane):
        fake_plane.arm_vehicle.side_effect = Exception("boom")
        r = plane_client.get("/command/arm")
        assert r.status_code == 500
        assert "ARM_COMMAND FAIL" in r.json()["detail"]

    def test_disarm(self, plane_client, fake_plane):
        r = plane_client.get("/command/disarm")
        assert r.status_code == 200
        assert_envelope(r.json(), "Disarmed vehicle")
        fake_plane.disarm_vehicle.assert_called_once_with()

    def test_takeoff(self, plane_client, fake_plane):
        r = plane_client.get(
            "/command/takeoff", params={"alt": 50, "pitch_deg": 20, "vtol": "false"}
        )
        assert r.status_code == 200
        assert_envelope(r.json(), "50.0 meters")
        fake_plane.takeoff.assert_called_once_with(50.0, pitch_deg=20.0, vtol=False)

    def test_takeoff_requires_alt(self, plane_client, fake_plane):
        r = plane_client.get("/command/takeoff")
        assert r.status_code == 422
        fake_plane.takeoff.assert_not_called()

    def test_land(self, plane_client, fake_plane):
        r = plane_client.get("/command/land")
        assert r.status_code == 200
        fake_plane.land.assert_called_once_with()

    def test_land_at(self, plane_client, fake_plane):
        r = plane_client.get(
            "/command/land_at", params={"lat": -15.84, "long": -47.92, "vtol": "true"}
        )
        assert r.status_code == 200
        assert_envelope(r.json(), "(-15.84, -47.92)")
        fake_plane.land_at.assert_called_once_with(-15.84, -47.92, 0.0, vtol=True)

    def test_rtl(self, plane_client, fake_plane):
        r = plane_client.get("/command/rtl")
        assert r.status_code == 200
        assert_envelope(r.json(), "Returned to launch")
        fake_plane.do_RTL.assert_called_once_with()

    def test_set_home(self, plane_client, fake_plane):
        r = plane_client.get("/command/set_home")
        assert r.status_code == 200
        fake_plane.set_home.assert_called_once_with()


class TestMovement:
    def test_go_to_gps(self, plane_client, fake_plane):
        r = plane_client.post("/movement/go_to_gps", json=GPS_BODY)
        assert r.status_code == 200
        assert_envelope(r.json(), "(-15.84, -47.92, 100.0)")
        fake_plane.go_to_gps.assert_called_once_with(-15.84, -47.92, 100.0)

    def test_go_to_gps_wait(self, plane_client, fake_plane):
        r = plane_client.post("/movement/go_to_gps_wait", json=GPS_BODY)
        assert r.status_code == 200
        assert_envelope(r.json(), "Arrived")
        fake_plane.go_to_gps_wait.assert_called_once_with(-15.84, -47.92, 100.0)

    def test_go_to_gps_malformed_body_is_422(self, plane_client, fake_plane):
        r = plane_client.post("/movement/go_to_gps", json={"lat": -15.84})
        assert r.status_code == 422
        fake_plane.go_to_gps.assert_not_called()

    def test_stop(self, plane_client, fake_plane):
        r = plane_client.get("/movement/stop")
        assert r.status_code == 200
        assert_envelope(r.json(), "loitering")
        fake_plane.stop.assert_called_once_with()


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
