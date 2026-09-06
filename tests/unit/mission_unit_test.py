"""Unit tests for the mission router: the full execute → running-scripts →
stop-script lifecycle without tmux.

subprocess.run is monkeypatched with a recorder, so the tests assert the
exact tmux argv the router issues instead of creating real sessions — CI
needs no tmux installed. The scripts_table fixture gives per-test state
isolation (the real table is a process-wide global).
"""

import shlex
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


class TestExecuteFailures:
    def test_execute_tmux_failure_is_500(self, copter_client, scripts_table, monkeypatch):
        def failing_run(cmd, **kwargs):
            return SimpleNamespace(returncode=1, stdout=b"", stderr=b"duplicate session")

        monkeypatch.setattr("uav_api.routers.common.mission.subprocess.run", failing_run)
        upload(copter_client)
        r = copter_client.post("/mission/execute-script/", json={"script_name": "test_script"})
        assert r.status_code == 500
        assert "duplicate session" in r.json()["detail"]
        # No phantom "running" entry for a session tmux never created.
        assert scripts_table == {}

    def test_execute_tmux_missing_is_503(self, copter_client, scripts_table, monkeypatch):
        def missing_run(cmd, **kwargs):
            raise FileNotFoundError("tmux")

        monkeypatch.setattr("uav_api.routers.common.mission.subprocess.run", missing_run)
        upload(copter_client)
        r = copter_client.post("/mission/execute-script/", json={"script_name": "test_script"})
        assert r.status_code == 503
        assert "tmux is not installed" in r.json()["detail"]
        assert scripts_table == {}

    def test_execute_quotes_paths_with_spaces(
        self, copter_client, copter_args, tmux_calls, tmp_path
    ):
        logs_dir = tmp_path / "logs with space"
        logs_dir.mkdir()
        # The get_args override returns this same Namespace by reference.
        copter_args.script_logs = str(logs_dir)

        upload(copter_client)
        r = copter_client.post("/mission/execute-script/", json={"script_name": "test_script"})
        assert r.status_code == 200

        assert tmux_calls[0][5:7] == ["bash", "-c"]
        command = tmux_calls[0][7]
        log_tokens = [t for t in shlex.split(command) if t.endswith(".log")]
        assert len(log_tokens) == 2
        assert all(str(logs_dir) in t for t in log_tokens)


class TestClear:
    def test_clear_scripts(self, copter_client, copter_args):
        upload(copter_client)
        upload(copter_client, name="other.sh", content=b"echo hi\n")
        r = copter_client.delete("/mission/clear-scripts")
        assert r.status_code == 200
        assert sorted(r.json()["removed"]) == ["other.sh", "test_script.py"]
        assert list(Path(copter_args.scripts_path).iterdir()) == []


class TestScriptLog:
    """script-log reads the files execute-script redirects the process into.
    tmux is mocked here, so no process writes them — the tests create the log
    files at the paths the router recorded in the scripts table."""

    def _run_and_write_logs(self, client, scripts_table, out="", err=""):
        upload(client)
        client.post("/mission/execute-script/", json={"script_name": "test_script"})
        entry = scripts_table["test_script.py"]
        Path(entry["out_log"]).write_text(out)
        Path(entry["err_log"]).write_text(err)
        return entry

    def test_reads_stdout_by_default(self, copter_client, scripts_table, tmux_calls):
        self._run_and_write_logs(copter_client, scripts_table, out="line 1\nline 2\n")
        r = copter_client.get("/mission/script-log", params={"script_name": "test_script"})
        assert r.status_code == 200
        body = r.json()
        assert body["script"] == "test_script.py"
        assert body["stream"] == "out"
        assert body["lines"] == ["line 1", "line 2"]
        # This endpoint deliberately mints no deprecated numeric code.
        assert "type" not in body

    def test_reads_stderr(self, copter_client, scripts_table, tmux_calls):
        self._run_and_write_logs(copter_client, scripts_table, out="out\n", err="boom\n")
        r = copter_client.get(
            "/mission/script-log", params={"script_name": "test_script", "stream": "err"}
        )
        assert r.status_code == 200
        assert r.json()["lines"] == ["boom"]

    def test_tail_keeps_the_newest_lines(self, copter_client, scripts_table, tmux_calls):
        self._run_and_write_logs(
            copter_client, scripts_table, out="".join(f"line {i}\n" for i in range(10))
        )
        r = copter_client.get(
            "/mission/script-log", params={"script_name": "test_script", "tail": 3}
        )
        assert r.status_code == 200
        assert r.json()["lines"] == ["line 7", "line 8", "line 9"]

    def test_partial_final_line_is_returned(self, copter_client, scripts_table, tmux_calls):
        # A log being written concurrently routinely ends without a newline.
        self._run_and_write_logs(copter_client, scripts_table, out="done\npartial")
        r = copter_client.get("/mission/script-log", params={"script_name": "test_script"})
        assert r.json()["lines"] == ["done", "partial"]

    def test_undecodable_bytes_do_not_fail_the_request(
        self, copter_client, scripts_table, tmux_calls
    ):
        entry = self._run_and_write_logs(copter_client, scripts_table)
        Path(entry["out_log"]).write_bytes(b"ok\n\xff\xfe\n")
        r = copter_client.get("/mission/script-log", params={"script_name": "test_script"})
        assert r.status_code == 200
        assert r.json()["lines"][0] == "ok"

    def test_empty_log_is_empty_list(self, copter_client, scripts_table, tmux_calls):
        self._run_and_write_logs(copter_client, scripts_table, out="")
        r = copter_client.get("/mission/script-log", params={"script_name": "test_script"})
        assert r.status_code == 200
        assert r.json()["lines"] == []

    def test_name_is_normalized_like_the_other_routes(
        self, copter_client, scripts_table, tmux_calls
    ):
        self._run_and_write_logs(copter_client, scripts_table, out="hi\n")
        # no .py suffix, plus a directory component to strip
        r = copter_client.get("/mission/script-log", params={"script_name": "../test_script"})
        assert r.status_code == 200
        assert r.json()["script"] == "test_script.py"

    def test_readable_after_stop(self, copter_client, scripts_table, tmux_calls):
        self._run_and_write_logs(copter_client, scripts_table, out="hi\n")
        copter_client.post("/mission/stop-script/", json={"script_name": "test_script"})
        # Stopped entries are retained, so post-flight review still works.
        r = copter_client.get("/mission/script-log", params={"script_name": "test_script"})
        assert r.status_code == 200
        assert r.json()["lines"] == ["hi"]

    def test_unknown_script_is_404(self, copter_client):
        r = copter_client.get("/mission/script-log", params={"script_name": "ghost"})
        assert r.status_code == 404
        assert "not found in scripts table" in r.json()["detail"]

    def test_missing_log_file_is_404(self, copter_client, scripts_table, tmux_calls):
        upload(copter_client)
        copter_client.post("/mission/execute-script/", json={"script_name": "test_script"})
        # tmux is mocked, so the redirect target was never created.
        r = copter_client.get("/mission/script-log", params={"script_name": "test_script"})
        assert r.status_code == 404
        assert "Log file" in r.json()["detail"]

    def test_missing_script_name_is_422(self, copter_client):
        assert copter_client.get("/mission/script-log").status_code == 422

    def test_invalid_stream_is_422(self, copter_client, scripts_table, tmux_calls):
        self._run_and_write_logs(copter_client, scripts_table, out="hi\n")
        r = copter_client.get(
            "/mission/script-log", params={"script_name": "test_script", "stream": "both"}
        )
        assert r.status_code == 422

    @pytest.mark.parametrize("tail", [0, 1001])
    def test_out_of_range_tail_is_422(self, copter_client, scripts_table, tmux_calls, tail):
        self._run_and_write_logs(copter_client, scripts_table, out="hi\n")
        r = copter_client.get(
            "/mission/script-log", params={"script_name": "test_script", "tail": tail}
        )
        assert r.status_code == 422
