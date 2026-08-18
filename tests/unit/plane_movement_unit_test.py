"""Unit tests for the plane movement router: HTTP contract + vehicle delegation."""

import pytest

from unit_helpers import assert_envelope

pytestmark = pytest.mark.plane

GPS_BODY = {"lat": -15.84, "long": -47.92, "alt": 100}


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
