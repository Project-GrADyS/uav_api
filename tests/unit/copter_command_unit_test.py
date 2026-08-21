"""Unit tests for the copter command router: HTTP contract + vehicle delegation."""

import pytest

from unit_helpers import assert_envelope

pytestmark = pytest.mark.copter


class TestArm:
    def test_arm(self, copter_client, fake_copter):
        r = copter_client.get("/command/arm")
        assert r.status_code == 200
        assert_envelope(r.json(), "Armed vehicle")
        fake_copter.change_mode.assert_called_once_with("GUIDED")
        fake_copter.wait_ready_to_arm.assert_called_once_with()
        fake_copter.arm_vehicle.assert_called_once_with()

    def test_arm_reports_disarmed_when_arming_did_not_stick(self, copter_client, fake_copter):
        fake_copter.armed.return_value = False
        r = copter_client.get("/command/arm")
        assert r.status_code == 200
        assert_envelope(r.json(), "Disarmed vehicle")

    def test_arm_failure_is_500(self, copter_client, fake_copter):
        fake_copter.arm_vehicle.side_effect = Exception("boom")
        r = copter_client.get("/command/arm")
        assert r.status_code == 500
        assert "ARM_COMMAND FAIL" in r.json()["detail"]


class TestFlight:
    def test_takeoff(self, copter_client, fake_copter):
        r = copter_client.get("/command/takeoff", params={"alt": 30})
        assert r.status_code == 200
        assert_envelope(r.json(), "30 meters")
        fake_copter.user_takeoff.assert_called_once_with(30)

    def test_takeoff_default_altitude(self, copter_client, fake_copter):
        r = copter_client.get("/command/takeoff")
        assert r.status_code == 200
        fake_copter.user_takeoff.assert_called_once_with(15)

    def test_land(self, copter_client, fake_copter):
        r = copter_client.get("/command/land")
        assert r.status_code == 200
        assert_envelope(r.json())
        fake_copter.land_and_disarm.assert_called_once_with()

    def test_rtl(self, copter_client, fake_copter):
        r = copter_client.get("/command/rtl")
        assert r.status_code == 200
        assert_envelope(r.json())
        fake_copter.do_RTL.assert_called_once_with()


class TestModes:
    def test_brake(self, copter_client, fake_copter):
        r = copter_client.get("/command/brake")
        assert r.status_code == 200
        fake_copter.change_mode.assert_called_once_with("BRAKE")

    def test_brake_mode_change_refused_is_500(self, copter_client, fake_copter):
        fake_copter.change_mode.return_value = False
        r = copter_client.get("/command/brake")
        assert r.status_code == 500
        assert "BRAKE_COMMAND FAIL" in r.json()["detail"]

    def test_guided(self, copter_client, fake_copter):
        r = copter_client.get("/command/guided")
        assert r.status_code == 200
        fake_copter.change_mode.assert_called_once_with("GUIDED")


class TestSetters:
    def test_set_air_speed(self, copter_client, fake_copter):
        r = copter_client.get("/command/set_air_speed", params={"new_v": 10})
        assert r.status_code == 200
        assert_envelope(r.json(), "10m/s")
        fake_copter.change_air_speed.assert_called_once_with(10)

    def test_set_ground_speed(self, copter_client, fake_copter):
        r = copter_client.get("/command/set_ground_speed", params={"new_v": 8})
        assert r.status_code == 200
        fake_copter.change_ground_speed.assert_called_once_with(8)

    def test_set_climb_speed(self, copter_client, fake_copter):
        r = copter_client.get("/command/set_climb_speed", params={"new_v": 4})
        assert r.status_code == 200
        fake_copter.change_climb_speed.assert_called_once_with(4)

    def test_set_descent_speed(self, copter_client, fake_copter):
        r = copter_client.get("/command/set_descent_speed", params={"new_v": 3})
        assert r.status_code == 200
        fake_copter.change_descent_speed.assert_called_once_with(3)

    def test_set_sim_speedup(self, copter_client, fake_copter):
        r = copter_client.get("/command/set_sim_speedup", params={"sim_factor": 2.5})
        assert r.status_code == 200
        fake_copter.set_parameter.assert_called_once_with("SIM_SPEEDUP", 2.5)

    def test_set_home(self, copter_client, fake_copter):
        r = copter_client.get("/command/set_home")
        assert r.status_code == 200
        fake_copter.set_home.assert_called_once_with()

    def test_missing_required_param_is_422(self, copter_client):
        r = copter_client.get("/command/set_air_speed")
        assert r.status_code == 422
