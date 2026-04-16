"""
Integration tests for the peripherical router (/peripherical/...).

Uses the session-scoped SITL server from conftest.py, which starts
already armed and hovering at 15 m altitude.

Since there is no camera hardware in SITL, these tests exercise only
the validation paths (disallowed commands, invalid resolution, missing
required parameters).
"""

from conftest import get


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
