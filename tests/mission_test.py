"""
Integration tests for the mission router endpoints.

Own SITL instance (port 8002, sysid 2), grounded — these tests only need the
API. Order: upload → list → execute → clear.

Uploaded scripts live on disk (~/uav_scripts) and persist across API
restarts, so leftovers are wiped before the module runs.
"""

import glob
import os

import pytest

from conftest import make_api_fixture

api = make_api_fixture(port=8002, sysid=2, flying=False)

SCRIPTS_PATH = os.path.expanduser("~/uav_scripts")


@pytest.fixture(scope="module", autouse=True)
def clean_test_scripts():
    """Remove test scripts left on disk by previous runs."""
    for path in glob.glob(os.path.join(SCRIPTS_PATH, "test_script.*")):
        os.remove(path)
    yield


class TestMissionWorkflow:
    """Ordered mission workflow: upload, list, execute, clear."""

    def test_upload_py_script(self, api):
        r = api.post(
            "/mission/upload-script",
            files={"file": ("test_script.py", b"print('hello')", "text/x-python")},
        )
        assert r.status_code == 200
        assert "test_script.py" in r.json()["info"]

    def test_upload_sh_script(self, api):
        r = api.post(
            "/mission/upload-script",
            files={"file": ("test_script.sh", b"echo hello", "text/x-shellscript")},
        )
        assert r.status_code == 200

    def test_upload_invalid_extension(self, api):
        r = api.post(
            "/mission/upload-script",
            files={"file": ("bad.txt", b"data", "text/plain")},
        )
        assert r.status_code == 400

    def test_list_scripts(self, api):
        # list-scripts only reports .py files, so the .sh upload won't appear
        r = api.get("/mission/list-scripts")
        assert r.status_code == 200
        assert "test_script.py" in r.json()["scripts"]

    def test_execute_existing_script(self, api):
        r = api.post("/mission/execute-script/", json={"script_name": "test_script.py"})
        assert r.status_code == 200
        assert "script" in r.json()

    def test_execute_missing_script(self, api):
        r = api.post("/mission/execute-script/", json={"script_name": "nonexistent.py"})
        assert r.status_code == 404

    def test_clear_scripts(self, api):
        r = api.delete("/mission/clear-scripts")
        assert r.status_code == 200
        removed = r.json()["removed"]
        # clear-scripts removes both .py and .sh uploads
        assert "test_script.py" in removed
        assert "test_script.sh" in removed

    def test_list_after_clear(self, api):
        r = api.get("/mission/list-scripts")
        assert r.status_code == 200
        assert "test_script.py" not in r.json()["scripts"]
