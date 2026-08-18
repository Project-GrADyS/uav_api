"""Unit tests for the plane command router: HTTP contract + vehicle delegation."""

import pytest

from unit_helpers import assert_envelope

pytestmark = pytest.mark.plane


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
