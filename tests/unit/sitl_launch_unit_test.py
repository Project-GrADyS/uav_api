"""Unit tests for SITL launch plumbing: the argv-list command builder and the
locations.txt merge/validation. No SITL is started."""

import pytest

from uav_api.args import parse_args
from uav_api.lifespan import build_sitl_command
from uav_api.setup import (
    CUSTOM_LOCATIONS,
    _parse_location_names,
    merge_locations,
    validate_location,
)


# --- build_sitl_command ---

def test_command_has_no_empty_argv_entries():
    args = parse_args(["--simulated", "--sysid", "3"])
    cmd = build_sitl_command(args, "sim_vehicle.py", "/logs")
    assert all(cmd)  # the old string-split injected "" entries


def test_paths_with_spaces_survive():
    args = parse_args(["--simulated"])
    cmd = build_sitl_command(args, "/path with space/sim_vehicle.py", "/logs dir")
    assert "/path with space/sim_vehicle.py" in cmd
    assert "--use-dir=/logs dir" in cmd


def test_gs_connections_each_get_an_out():
    args = parse_args([
        "--simulated", "--gs_connection", "1.2.3.4:14550", "5.6.7.8:14550",
    ])
    cmd = build_sitl_command(args, "sim_vehicle.py", "/logs")
    assert cmd.count("--out") == 3  # uav_connection + 2 ground stations


def test_headless_daemonizes_mavproxy_and_drops_the_terminal():
    args = parse_args(["--simulated", "--headless"])
    cmd = build_sitl_command(args, "sim_vehicle.py", "/logs")
    assert cmd[0] == "sim_vehicle.py"
    assert "--mavproxy-args=--daemon" in cmd


def test_terminal_is_configurable_and_shell_split():
    args = parse_args(["--simulated", "--terminal", "gnome-terminal --"])
    cmd = build_sitl_command(args, "sim_vehicle.py", "/logs")
    assert cmd[:2] == ["gnome-terminal", "--"]


def test_default_terminal_is_xterm():
    args = parse_args(["--simulated"])
    cmd = build_sitl_command(args, "sim_vehicle.py", "/logs")
    assert cmd[:2] == ["xterm", "-e"]


# --- merge_locations ---

def test_merge_creates_file_with_all_entries(tmp_path):
    path = str(tmp_path / "locations.txt")
    merge_locations(path, CUSTOM_LOCATIONS)
    assert _parse_location_names(path) == set(CUSTOM_LOCATIONS)


def test_merge_preserves_user_entries_and_appends_only_missing(tmp_path):
    path = tmp_path / "locations.txt"
    # no trailing newline: the append must not glue onto the last line
    path.write_text("MyField=1.0,2.0,100,0\nAbraDF=-15.840081,-47.926642,1042,30")
    merge_locations(str(path), CUSTOM_LOCATIONS)
    content = path.read_text()
    assert "MyField=1.0,2.0,100,0" in content
    assert content.count("AbraDF=") == 1
    assert "1042,30Abradf1" not in content
    assert _parse_location_names(str(path)) >= set(CUSTOM_LOCATIONS)


def test_merge_is_idempotent(tmp_path):
    path = str(tmp_path / "locations.txt")
    merge_locations(path, CUSTOM_LOCATIONS)
    first = open(path).read()
    merge_locations(path, CUSTOM_LOCATIONS)
    assert open(path).read() == first


# --- validate_location ---

def make_locations_file(tmp_path):
    path = str(tmp_path / "locations.txt")
    merge_locations(path, CUSTOM_LOCATIONS)
    return path


def test_known_custom_location_passes(tmp_path):
    args = parse_args(["--simulated", "--location", "AbraDF"])
    validate_location(args, make_locations_file(tmp_path))


def test_unknown_location_without_ardupilot_path_only_warns(tmp_path, caplog):
    args = parse_args(["--simulated", "--location", "Nowhere"])
    with caplog.at_level("WARNING", logger="SYSTEM"):
        validate_location(args, make_locations_file(tmp_path))
    assert any("Nowhere" in record.message for record in caplog.records)


def test_unknown_location_with_builtins_visible_exits(tmp_path):
    ardupilot = tmp_path / "ardupilot"
    (ardupilot / "Tools" / "autotest").mkdir(parents=True)
    (ardupilot / "Tools" / "autotest" / "locations.txt").write_text(
        "CMAC=-35.36,149.16,584,353\n"
    )
    args = parse_args([
        "--simulated", "--location", "Nowhere", "--ardupilot_path", str(ardupilot),
    ])
    with pytest.raises(SystemExit):
        validate_location(args, make_locations_file(tmp_path))


def test_builtin_location_passes(tmp_path):
    ardupilot = tmp_path / "ardupilot"
    (ardupilot / "Tools" / "autotest").mkdir(parents=True)
    (ardupilot / "Tools" / "autotest" / "locations.txt").write_text(
        "CMAC=-35.36,149.16,584,353\n"
    )
    args = parse_args([
        "--simulated", "--location", "CMAC", "--ardupilot_path", str(ardupilot),
    ])
    validate_location(args, make_locations_file(tmp_path))
