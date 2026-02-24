"""
Tests for the mission router (uav_api/routers/mission.py).

Run with:
    pytest tests/mission_test.py -v
"""

import argparse
import io
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from uav_api.router_dependencies import get_args
from uav_api.routers.mission import mission_router


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def scripts_dir(tmp_path):
    d = tmp_path / "scripts"
    d.mkdir()
    return d


@pytest.fixture
def script_logs_dir(tmp_path):
    d = tmp_path / "logs"
    d.mkdir()
    return d


@pytest.fixture
def test_args(scripts_dir, script_logs_dir):
    return argparse.Namespace(
        sysid=1,
        scripts_path=str(scripts_dir),
        script_logs=str(script_logs_dir),
        python_path="python3",
    )


@pytest.fixture
def client(test_args):
    app = FastAPI()
    app.include_router(mission_router)
    app.dependency_overrides[get_args] = lambda: test_args
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _upload(client, filename: str, content: bytes = b"print('hello')"):
    return client.post(
        "/mission/upload-script",
        files={"file": (filename, io.BytesIO(content), "text/plain")},
    )


# ---------------------------------------------------------------------------
# POST /mission/upload-script
# ---------------------------------------------------------------------------

class TestUploadScript:
    def test_upload_valid_py(self, client, scripts_dir):
        r = _upload(client, "my_script.py")
        assert r.status_code == 200
        body = r.json()
        assert body["device"] == "uav"
        assert body["id"] == "1"
        assert body["type"] == 44
        assert (scripts_dir / "my_script.py").exists()

    def test_upload_valid_sh(self, client, scripts_dir):
        r = _upload(client, "my_script.sh", b"#!/bin/bash\necho hi")
        assert r.status_code == 200
        assert (scripts_dir / "my_script.sh").exists()

    def test_upload_invalid_extension(self, client):
        r = _upload(client, "data.txt")
        assert r.status_code == 400

    def test_upload_directory_traversal(self, client, scripts_dir):
        # Filename ../../evil.py must be sanitised to evil.py
        r = _upload(client, "../../evil.py")
        assert r.status_code == 200
        # The file must land inside scripts_dir, not two levels up
        assert (scripts_dir / "evil.py").exists()


# ---------------------------------------------------------------------------
# GET /mission/list-scripts
# ---------------------------------------------------------------------------

class TestListScripts:
    def test_list_empty(self, client):
        r = client.get("/mission/list-scripts")
        assert r.status_code == 200
        body = r.json()
        assert body["device"] == "uav"
        assert body["id"] == "1"
        assert body["type"] == 42
        assert body["scripts"] == []

    def test_list_py_files(self, client, scripts_dir):
        (scripts_dir / "a.py").write_text("pass")
        (scripts_dir / "b.py").write_text("pass")
        r = client.get("/mission/list-scripts")
        assert r.status_code == 200
        assert sorted(r.json()["scripts"]) == ["a.py", "b.py"]

    def test_list_excludes_sh(self, client, scripts_dir):
        (scripts_dir / "a.py").write_text("pass")
        (scripts_dir / "b.sh").write_text("#!/bin/bash")
        r = client.get("/mission/list-scripts")
        assert r.status_code == 200
        assert r.json()["scripts"] == ["a.py"]


# ---------------------------------------------------------------------------
# POST /mission/execute-script/
# ---------------------------------------------------------------------------

class TestExecuteScript:
    def test_execute_missing_script(self, client):
        r = client.post("/mission/execute-script/", json={"script_name": "ghost.py"})
        assert r.status_code == 404

    def test_execute_existing_script_new_session(self, client, scripts_dir):
        (scripts_dir / "run.py").write_text("pass")
        mock_no_session = MagicMock(returncode=1)  # has-session → not found

        with patch("uav_api.routers.mission.subprocess.run", return_value=mock_no_session):
            r = client.post("/mission/execute-script/", json={"script_name": "run.py"})

        assert r.status_code == 200
        body = r.json()
        assert body["device"] == "uav"
        assert body["id"] == "1"
        assert body["type"] == 46
        assert body["script"] == "run.py"

    def test_execute_existing_script_session_running(self, client, scripts_dir):
        (scripts_dir / "run.py").write_text("pass")
        mock_has_session = MagicMock(returncode=0)  # has-session → already exists

        with patch("uav_api.routers.mission.subprocess.run", return_value=mock_has_session):
            r = client.post("/mission/execute-script/", json={"script_name": "run.py"})

        assert r.status_code == 200
        assert r.json()["script"] == "run.py"

    def test_execute_appends_py_extension(self, client, scripts_dir):
        (scripts_dir / "run.py").write_text("pass")
        mock = MagicMock(returncode=1)

        with patch("uav_api.routers.mission.subprocess.run", return_value=mock):
            r = client.post("/mission/execute-script/", json={"script_name": "run"})

        assert r.status_code == 200
        assert r.json()["script"] == "run.py"


# ---------------------------------------------------------------------------
# DELETE /mission/clear
# ---------------------------------------------------------------------------

class TestClearScripts:
    def test_clear_empty_dir(self, client):
        r = client.delete("/mission/clear")
        assert r.status_code == 200
        body = r.json()
        assert body["device"] == "uav"
        assert body["id"] == "1"
        assert body["type"] == 48
        assert body["removed"] == []

    def test_clear_removes_py_and_sh(self, client, scripts_dir):
        (scripts_dir / "a.py").write_text("pass")
        (scripts_dir / "b.sh").write_text("#!/bin/bash")
        r = client.delete("/mission/clear")
        assert r.status_code == 200
        body = r.json()
        assert sorted(body["removed"]) == ["a.py", "b.sh"]
        assert not (scripts_dir / "a.py").exists()
        assert not (scripts_dir / "b.sh").exists()

    def test_clear_twice_is_idempotent(self, client, scripts_dir):
        (scripts_dir / "a.py").write_text("pass")
        client.delete("/mission/clear")
        r = client.delete("/mission/clear")
        assert r.status_code == 200
        assert r.json()["removed"] == []

    def test_clear_leaves_other_files(self, client, scripts_dir):
        (scripts_dir / "a.py").write_text("pass")
        (scripts_dir / "readme.txt").write_text("notes")
        r = client.delete("/mission/clear")
        assert r.status_code == 200
        assert r.json()["removed"] == ["a.py"]
        assert (scripts_dir / "readme.txt").exists()
