"""
Integration tests for the mission router endpoints.

Tests run against a session-scoped SITL server (see conftest.py).
Order: upload → list → execute → clear.
"""

import requests
from conftest import get, post, delete, BASE_URL


class TestMissionWorkflow:
    """Ordered mission workflow: upload, list, execute, clear."""

    def test_upload_py_script(self, api_server):
        r = requests.post(
            f"{BASE_URL}/mission/upload-script",
            files={"file": ("test_script.py", b"print('hello')", "text/x-python")},
            timeout=10,
        )
        assert r.status_code == 200
        assert "test_script.py" in r.json()["info"]

    def test_upload_sh_script(self, api_server):
        r = requests.post(
            f"{BASE_URL}/mission/upload-script",
            files={"file": ("test_script.sh", b"echo hello", "text/x-shellscript")},
            timeout=10,
        )
        assert r.status_code == 200

    def test_upload_invalid_extension(self, api_server):
        r = requests.post(
            f"{BASE_URL}/mission/upload-script",
            files={"file": ("bad.txt", b"data", "text/plain")},
            timeout=10,
        )
        assert r.status_code == 400

    def test_list_scripts(self, api_server):
        r = get("/mission/list-scripts")
        assert r.status_code == 200
        assert "test_script.py" in r.json()["scripts"]

    def test_execute_existing_script(self, api_server):
        r = post("/mission/execute-script/", json={"script_name": "test_script.py"})
        assert r.status_code == 200
        assert "script" in r.json()

    def test_execute_missing_script(self, api_server):
        r = post("/mission/execute-script/", json={"script_name": "nonexistent.py"})
        assert r.status_code == 404

    def test_clear_scripts(self, api_server):
        r = delete("/mission/clear")
        assert r.status_code == 200
        assert len(r.json()["removed"]) > 0

    def test_list_after_clear(self, api_server):
        r = get("/mission/list-scripts")
        assert r.status_code == 200
        assert "test_script.py" not in r.json()["scripts"]
