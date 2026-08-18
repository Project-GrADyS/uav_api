"""Unit tests for the peripherical router.

The SITL suite can only exercise take_photo's validation paths (no camera in
SITL); here the happy path and the empty-output failure are covered by
monkeypatching subprocess.run in the router module.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from unit_helpers import assert_envelope


@pytest.fixture
def camera_calls(monkeypatch):
    """Record camera invocations and write fake JPEG bytes to the output path
    (the temp file path is the last element of every whitelisted command)."""
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        Path(cmd[-1]).write_bytes(b"JPEGDATA")
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr("uav_api.routers.copter_peripherical.subprocess.run", fake_run)
    return calls


@pytest.fixture
def broken_camera(monkeypatch):
    """Camera command runs but produces no output file."""
    def fake_run(cmd, **kwargs):
        return SimpleNamespace(returncode=1, stdout=b"", stderr=b"no camera detected")

    monkeypatch.setattr("uav_api.routers.copter_peripherical.subprocess.run", fake_run)


class TestTakePhoto:
    def test_take_photo(self, copter_client, camera_calls):
        r = copter_client.get("/peripherical/take_photo", params={"command": "fswebcam"})
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/jpeg"
        assert r.content == b"JPEGDATA"
        assert camera_calls[0][0] == "fswebcam"
        assert "1280x720" in camera_calls[0]

    def test_disallowed_command_is_400_without_running_anything(
        self, copter_client, camera_calls
    ):
        r = copter_client.get("/peripherical/take_photo", params={"command": "rm"})
        assert r.status_code == 400
        assert camera_calls == []

    def test_invalid_resolution_is_400(self, copter_client, camera_calls):
        r = copter_client.get(
            "/peripherical/take_photo",
            params={"command": "fswebcam", "resolution": "abc"},
        )
        assert r.status_code == 400
        assert camera_calls == []

    def test_missing_command_is_422(self, copter_client, camera_calls):
        r = copter_client.get("/peripherical/take_photo")
        assert r.status_code == 422

    def test_no_output_file_is_500(self, copter_client, broken_camera):
        r = copter_client.get("/peripherical/take_photo", params={"command": "fswebcam"})
        assert r.status_code == 500
        assert "no camera detected" in r.json()["detail"]


class TestServoOutput:
    def test_servo_output(self, copter_client, fake_copter):
        r = copter_client.post("/peripherical/servo_output", json={"channel": 5, "pwm": 1500})
        assert r.status_code == 200
        assert_envelope(r.json(), "Servo 5 set to 1500 PWM")
        fake_copter.set_servo.assert_called_once_with(5, 1500)

    def test_servo_output_malformed_body_is_422(self, copter_client, fake_copter):
        r = copter_client.post("/peripherical/servo_output", json={"channel": 5})
        assert r.status_code == 422
        fake_copter.set_servo.assert_not_called()

    def test_servo_output_failure_is_500(self, copter_client, fake_copter):
        fake_copter.set_servo.side_effect = Exception("no link")
        r = copter_client.post("/peripherical/servo_output", json={"channel": 5, "pwm": 1500})
        assert r.status_code == 500
        assert "SERVO_OUTPUT FAIL" in r.json()["detail"]
