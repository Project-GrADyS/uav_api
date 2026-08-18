"""Unit tests for the copter movement router: HTTP contract + vehicle delegation.

Covers the endpoints the SITL suite leaves untested: go_to_ned_wait,
drive_wait and set_yaw_rate, plus direct coverage for set_heading.
"""

from unit_helpers import NED_POSITION, assert_envelope

GPS_BODY = {"lat": -15.84, "long": -47.92, "alt": 30}
NED_BODY = {"x": 10.0, "y": 5.0, "z": -20.0}
VEL_BODY = {"vx": 1.0, "vy": 2.0, "vz": -0.5}


class TestGps:
    def test_go_to_gps(self, copter_client, fake_copter):
        r = copter_client.post("/movement/go_to_gps/", json=GPS_BODY)
        assert r.status_code == 200
        assert_envelope(r.json(), "(-15.84, -47.92, 30.0)")
        fake_copter.go_to_gps.assert_called_once_with(-15.84, -47.92, 30.0, False)

    def test_go_to_gps_look_at_target(self, copter_client, fake_copter):
        r = copter_client.post("/movement/go_to_gps/", json={**GPS_BODY, "look_at_target": True})
        assert r.status_code == 200
        fake_copter.go_to_gps.assert_called_once_with(-15.84, -47.92, 30.0, True)

    def test_go_to_gps_wait(self, copter_client, fake_copter):
        r = copter_client.post("/movement/go_to_gps_wait", json=GPS_BODY)
        assert r.status_code == 200
        assert_envelope(r.json(), "Arrived")
        fake_copter.go_to_gps.assert_called_once_with(-15.84, -47.92, 30.0, False)
        fake_copter.mav_location.assert_called_once_with(-15.84, -47.92, 30.0)
        fake_copter.wait_location.assert_called_once_with(
            fake_copter.mav_location.return_value, timeout=60
        )

    def test_go_to_gps_failure_is_500(self, copter_client, fake_copter):
        fake_copter.go_to_gps.side_effect = Exception("boom")
        r = copter_client.post("/movement/go_to_gps/", json=GPS_BODY)
        assert r.status_code == 500
        assert "GO_TO FAIL" in r.json()["detail"]


class TestNed:
    def test_go_to_ned(self, copter_client, fake_copter):
        r = copter_client.post("/movement/go_to_ned", json=NED_BODY)
        assert r.status_code == 200
        assert_envelope(r.json(), "(10.0, 5.0, -20.0)")
        fake_copter.go_to_ned.assert_called_once_with(10.0, 5.0, -20.0, look_at_target=False)

    def test_go_to_ned_wait(self, copter_client, fake_copter):
        r = copter_client.post("/movement/go_to_ned_wait", json=NED_BODY)
        assert r.status_code == 200
        assert_envelope(r.json(), "Arrived")
        fake_copter.go_to_ned.assert_called_once_with(10.0, 5.0, -20.0, look_at_target=False)
        fake_copter.wait_ned_position.assert_called_once()
        target = fake_copter.wait_ned_position.call_args[0][0]
        assert (target.x, target.y, target.z) == (10.0, 5.0, -20.0)

    def test_drive(self, copter_client, fake_copter):
        r = copter_client.post("/movement/drive", json={"x": 3.0, "y": 4.0, "z": -1.0})
        assert r.status_code == 200
        assert_envelope(r.json(), "driving")
        fake_copter.drive_ned.assert_called_once_with(3.0, 4.0, -1.0, look_at_target=False)

    def test_drive_wait(self, copter_client, fake_copter):
        # Displacement is relative: target = current NED position + requested delta.
        r = copter_client.post("/movement/drive_wait", json={"x": 3.0, "y": 4.0, "z": -1.0})
        assert r.status_code == 200
        expected = (NED_POSITION.x + 3.0, NED_POSITION.y + 4.0, NED_POSITION.z - 1.0)
        assert_envelope(r.json(), str(expected))
        fake_copter.drive_ned.assert_called_once_with(3.0, 4.0, -1.0, look_at_target=False)
        target = fake_copter.wait_ned_position.call_args[0][0]
        assert (target.x, target.y, target.z) == expected

    def test_travel_at_ned(self, copter_client, fake_copter):
        r = copter_client.post("/movement/travel_at_ned", json=VEL_BODY)
        assert r.status_code == 200
        assert_envelope(r.json(), "(1.0, 2.0, -0.5)")
        fake_copter.travel_at_ned.assert_called_once_with(1.0, 2.0, -0.5, look_at_target=False)

    def test_malformed_body_is_422(self, copter_client, fake_copter):
        r = copter_client.post("/movement/go_to_ned", json={"x": 1.0, "y": 2.0})
        assert r.status_code == 422
        fake_copter.go_to_ned.assert_not_called()


class TestYaw:
    def test_set_heading(self, copter_client, fake_copter):
        r = copter_client.get("/movement/set_heading", params={"heading": 90})
        assert r.status_code == 200
        assert_envelope(r.json(), "90.0 degrees")
        fake_copter.set_heading.assert_called_once_with(90.0)

    def test_set_yaw_rate(self, copter_client, fake_copter):
        r = copter_client.get("/movement/set_yaw_rate", params={"yaw_rate": 15})
        assert r.status_code == 200
        assert_envelope(r.json(), "15.0 deg/s")
        fake_copter.set_yaw_rate.assert_called_once_with(15.0)
