"""
Integration tests for the peripherical router (/peripherical/...).

Uses the session-scoped SITL server from conftest.py, which starts
already armed and hovering at 15 m altitude.

Since there is no camera hardware in SITL, these tests exercise only
the validation paths (disallowed commands, invalid resolution, missing
required parameters).
"""

from conftest import get, post


class TestTakePhotoValidation:

    def test_disallowed_command(self, api_server):
        r = get("/peripherical/take_photo", params={"command": "evil"})
        assert r.status_code == 400
        assert "not allowed" in r.json()["detail"].lower()

    def test_invalid_resolution(self, api_server):
        r = get("/peripherical/take_photo", params={
            "command": "fswebcam",
            "resolution": "abc",
        })
        assert r.status_code == 400

    def test_missing_command_param(self, api_server):
        r = get("/peripherical/take_photo")
        assert r.status_code == 422


class TestServoOutput:

    def test_servo_output(self, api_server):
        r = post("/peripherical/servo_output", json={"channel": 9, "pwm": 1500})
        assert r.status_code == 200
        body = r.json()
        assert "servo" in body["result"].lower()
        assert "1500" in body["result"]

    def test_servo_output_missing_params(self, api_server):
        r = post("/peripherical/servo_output", json={})
        assert r.status_code == 422
