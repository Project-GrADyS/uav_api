"""
Integration tests for the mission router endpoints.

Own SITL instance (port 8002, sysid 2), grounded — these tests only need the
API. Order: upload → list → execute → clear.

Uploaded scripts live on disk (~/.uav_api/scripts) and persist across API
restarts, so leftovers are wiped before the module runs.
"""

import glob
import os
import time

import pytest

from conftest import make_api_fixture

pytestmark = [pytest.mark.sitl, pytest.mark.copter]

api = make_api_fixture(port=8002, sysid=2, flying=False)

SCRIPTS_PATH = os.path.expanduser("~/.uav_api/scripts")


@pytest.fixture(scope="module", autouse=True)
def clean_test_scripts():
    """Remove test scripts left on disk by previous runs."""
    for pattern in ("test_script.*", "lifecycle_script.*", "short_script.*", "log_script.*"):
        for path in glob.glob(os.path.join(SCRIPTS_PATH, pattern)):
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


# A plain sleep loop: tmux's C-c delivers KeyboardInterrupt, which exits it.
LONG_RUNNING_SCRIPT = b"import time\nwhile True:\n    time.sleep(1)\n"
SHORT_SCRIPT = b"import time\ntime.sleep(3)\n"


def running_script_names(api):
    r = api.get("/mission/running-scripts")
    assert r.status_code == 200
    return [entry["script"] for entry in r.json()["scripts"]]


class TestScriptLifecycle:
    """Ordered execute → running-scripts → stop-script lifecycle against real
    tmux sessions (the unit layer asserts the tmux argv; this asserts the
    end-to-end state transitions)."""

    def test_execute_shows_in_running_scripts(self, api):
        r = api.post(
            "/mission/upload-script",
            files={"file": ("lifecycle_script.py", LONG_RUNNING_SCRIPT, "text/x-python")},
        )
        assert r.status_code == 200

        r = api.post("/mission/execute-script/", json={"script_name": "lifecycle_script.py"})
        assert r.status_code == 200

        r = api.get("/mission/running-scripts")
        assert r.status_code == 200
        entries = [e for e in r.json()["scripts"] if e["script"] == "lifecycle_script.py"]
        assert len(entries) == 1
        assert entries[0]["session"].startswith("UAV_API_2-lifecycle_script_py-")
        assert entries[0]["started_at"]

    def test_execute_while_running_is_400(self, api):
        r = api.post("/mission/execute-script/", json={"script_name": "lifecycle_script.py"})
        assert r.status_code == 400

    def test_stop_script(self, api):
        r = api.post("/mission/stop-script/", json={"script_name": "lifecycle_script.py"})
        assert r.status_code == 200
        assert r.json()["info"] == "Stopped"
        assert "lifecycle_script.py" not in running_script_names(api)

    def test_stop_again_is_400(self, api):
        r = api.post("/mission/stop-script/", json={"script_name": "lifecycle_script.py"})
        assert r.status_code == 400

    def test_stop_unknown_script_is_404(self, api):
        r = api.post("/mission/stop-script/", json={"script_name": "ghost.py"})
        assert r.status_code == 404

    def test_watcher_detects_natural_exit(self, api):
        """The scripts watcher (2s tmux poll) must flip a script that exits on
        its own from running to stopped — the only end-to-end coverage of
        scripts_watcher_loop."""
        r = api.post(
            "/mission/upload-script",
            files={"file": ("short_script.py", SHORT_SCRIPT, "text/x-python")},
        )
        assert r.status_code == 200
        r = api.post("/mission/execute-script/", json={"script_name": "short_script.py"})
        assert r.status_code == 200

        deadline = time.time() + 20
        while time.time() < deadline:
            if "short_script.py" not in running_script_names(api):
                return
            time.sleep(1)
        raise AssertionError("watcher never marked short_script.py as stopped")

    def test_lifecycle_cleanup(self, api):
        r = api.delete("/mission/clear-scripts")
        assert r.status_code == 200


# Writes to both streams, then stays alive so the log can be read mid-run.
LOGGING_SCRIPT = (
    b"import sys, time\n"
    b"print('hello stdout', flush=True)\n"
    b"print('hello stderr', file=sys.stderr, flush=True)\n"
    b"time.sleep(30)\n"
)


class TestScriptLog:
    """End-to-end: a real tmux session writes real log files, and script-log
    reads them both while running and after the script is stopped. The edge
    cases (tail, normalization, 404s, 422s) live in the unit layer."""

    def test_reads_real_logs_while_running(self, api):
        r = api.post(
            "/mission/upload-script",
            files={"file": ("log_script.py", LOGGING_SCRIPT, "text/x-python")},
        )
        assert r.status_code == 200
        r = api.post("/mission/execute-script/", json={"script_name": "log_script.py"})
        assert r.status_code == 200

        # tmux needs a moment to start the interpreter and flush the first line.
        deadline = time.time() + 15
        while time.time() < deadline:
            r = api.get("/mission/script-log", params={"script_name": "log_script.py"})
            if r.status_code == 200 and "hello stdout" in r.json()["lines"]:
                break
            time.sleep(1)
        else:
            raise AssertionError("script-log never returned the script's stdout")

        r = api.get(
            "/mission/script-log", params={"script_name": "log_script.py", "stream": "err"}
        )
        assert r.status_code == 200
        assert "hello stderr" in r.json()["lines"]

    def test_log_survives_stop(self, api):
        r = api.post("/mission/stop-script/", json={"script_name": "log_script.py"})
        assert r.status_code == 200
        assert "log_script.py" not in running_script_names(api)

        r = api.get("/mission/script-log", params={"script_name": "log_script.py"})
        assert r.status_code == 200
        assert "hello stdout" in r.json()["lines"]

    def test_script_log_cleanup(self, api):
        assert api.delete("/mission/clear-scripts").status_code == 200
