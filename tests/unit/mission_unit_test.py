"""Unit tests for the mission router: the full execute → running-scripts →
stop-script lifecycle without tmux.

subprocess.run is monkeypatched with a recorder, so the tests assert the
exact tmux argv the router issues instead of creating real sessions — CI
needs no tmux installed. The scripts_table fixture gives per-test state
isolation (the real table is a process-wide global).
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from unit_helpers import SYSID

pytestmark = pytest.mark.copter


@pytest.fixture
def tmux_calls(monkeypatch):
    """Record tmux invocations; also neutralize the 1s sleep in stop-script."""
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr("uav_api.routers.common.mission.subprocess.run", fake_run)
    monkeypatch.setattr("uav_api.routers.common.mission.time.sleep", lambda s: None)
    return calls


def upload(client, name="test_script.py", content=b"print('hi')\n"):
    return client.post("/mission/upload-script", files={"file": (name, content)})


class TestUpload:
    def test_upload_py(self, copter_client, copter_args):
        r = upload(copter_client)
        assert r.status_code == 200
        assert (Path(copter_args.scripts_path) / "test_script.py").exists()

    def test_upload_rejects_other_extensions(self, copter_client):
        r = upload(copter_client, name="notes.txt")
        assert r.status_code == 400

    def test_upload_sanitizes_path_traversal(self, copter_client, copter_args):
        r = upload(copter_client, name="../../evil.py")
        assert r.status_code == 200
        assert (Path(copter_args.scripts_path) / "evil.py").exists()

    def test_list_scripts(self, copter_client):
        upload(copter_client)
        r = copter_client.get("/mission/list-scripts")
        assert r.status_code == 200
        assert r.json()["scripts"] == ["test_script.py"]


class TestLifecycle:
    def test_execute_starts_tmux_session_and_tracks_it(
        self, copter_client, scripts_table, tmux_calls
    ):
        upload(copter_client)
        r = copter_client.post("/mission/execute-script/", json={"script_name": "test_script"})
        assert r.status_code == 200
        assert r.json()["script"] == "test_script.py"

        entry = scripts_table["test_script.py"]
        assert entry["status"] == "running"
        assert entry["session"].startswith(f"UAV_API_{SYSID}-test_script_py-")
        assert entry["started_at"] is not None
        assert entry["stopped_at"] is None

        assert tmux_calls[0][:4] == ["tmux", "new-session", "-d", "-s"]
        assert tmux_calls[0][4] == entry["session"]

    def test_execute_while_running_is_400(self, copter_client, tmux_calls):
        upload(copter_client)
        assert copter_client.post(
            "/mission/execute-script/", json={"script_name": "test_script"}
        ).status_code == 200
        r = copter_client.post("/mission/execute-script/", json={"script_name": "test_script"})
        assert r.status_code == 400
        assert "already running" in r.json()["detail"]

    def test_execute_missing_script_is_404(self, copter_client, tmux_calls):
        r = copter_client.post("/mission/execute-script/", json={"script_name": "nope"})
        assert r.status_code == 404
        assert tmux_calls == []

    def test_running_scripts_lists_only_running(self, copter_client, scripts_table, tmux_calls):
        upload(copter_client)
        copter_client.post("/mission/execute-script/", json={"script_name": "test_script"})
        r = copter_client.get("/mission/running-scripts")
        assert r.status_code == 200
        scripts = r.json()["scripts"]
        assert len(scripts) == 1
        assert scripts[0]["script"] == "test_script.py"
        assert scripts[0]["session"] == scripts_table["test_script.py"]["session"]

    def test_stop_script(self, copter_client, scripts_table, tmux_calls):
        upload(copter_client)
        copter_client.post("/mission/execute-script/", json={"script_name": "test_script"})
        session = scripts_table["test_script.py"]["session"]

        r = copter_client.post("/mission/stop-script/", json={"script_name": "test_script"})
        assert r.status_code == 200
        assert r.json()["info"] == "Stopped"

        entry = scripts_table["test_script.py"]
        assert entry["status"] == "stopped"
        assert entry["stopped_at"] is not None

        # Graceful interrupt first (C-c lets finally/atexit handlers run),
        # then the session is killed.
        assert ["tmux", "send-keys", "-t", session, "C-c", "C-m"] in tmux_calls
        assert ["tmux", "kill-session", "-t", session] in tmux_calls

        r = copter_client.get("/mission/running-scripts")
        assert r.json()["scripts"] == []

    def test_stop_twice_is_400(self, copter_client, tmux_calls):
        upload(copter_client)
        copter_client.post("/mission/execute-script/", json={"script_name": "test_script"})
        copter_client.post("/mission/stop-script/", json={"script_name": "test_script"})
        r = copter_client.post("/mission/stop-script/", json={"script_name": "test_script"})
        assert r.status_code == 400
        assert "not running" in r.json()["detail"]

    def test_stop_unknown_script_is_404(self, copter_client, tmux_calls):
        r = copter_client.post("/mission/stop-script/", json={"script_name": "ghost"})
        assert r.status_code == 404


class TestClear:
    def test_clear_scripts(self, copter_client, copter_args):
        upload(copter_client)
        upload(copter_client, name="other.sh", content=b"echo hi\n")
        r = copter_client.delete("/mission/clear-scripts")
        assert r.status_code == 200
        assert sorted(r.json()["removed"]) == ["other.sh", "test_script.py"]
        assert list(Path(copter_args.scripts_path).iterdir()) == []
