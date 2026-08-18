"""
Integration tests for the peripherical router (/peripherical/...).

Own SITL instance (port 8004, sysid 4), grounded — these endpoints need a
MAVLink link but no flight.

Since there is no camera hardware in SITL, the take_photo tests exercise
only the validation paths (disallowed commands, invalid resolution, missing
required parameters).
"""

import pytest

from conftest import make_api_fixture

pytestmark = pytest.mark.sitl

api = make_api_fixture(port=8004, sysid=4, flying=False)


class TestTakePhotoValidation:

    def test_disallowed_command(self, api):
        r = api.get("/peripherical/take_photo", params={"command": "evil"})
        assert r.status_code == 400
        assert "not allowed" in r.json()["detail"].lower()

    def test_invalid_resolution(self, api):
        r = api.get("/peripherical/take_photo", params={
            "command": "fswebcam",
            "resolution": "abc",
        })
        assert r.status_code == 400

    def test_missing_command_param(self, api):
        r = api.get("/peripherical/take_photo")
        assert r.status_code == 422


class TestServoOutput:

    def test_servo_output(self, api):
        r = api.post("/peripherical/servo_output", json={"channel": 9, "pwm": 1500})
        assert r.status_code == 200
        body = r.json()
        assert "servo" in body["result"].lower()
        assert "1500" in body["result"]

    def test_servo_output_missing_params(self, api):
        r = api.post("/peripherical/servo_output", json={})
        assert r.status_code == 422
