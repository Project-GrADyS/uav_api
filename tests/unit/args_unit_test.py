"""Unit tests for parse_args: CLI flag semantics and config-file handling
(missing files, section validation, key coercion). No SITL, no server."""

import pytest

from uav_api.args import parse_args


def write_ini(tmp_path, content):
    path = tmp_path / "uav-api.ini"
    path.write_text(content)
    return str(path)


# --- --simulated flag semantics (#16) ---

def test_simulated_defaults_off():
    assert parse_args([]).simulated is False


def test_simulated_is_a_bare_flag():
    assert parse_args(["--simulated"]).simulated is True


def test_simulated_rejects_a_value():
    # The old type=bool form made "--simulated false" silently mean True.
    with pytest.raises(SystemExit):
        parse_args(["--simulated", "true"])


# --- config file failure modes (#21) ---

def test_missing_config_file_exits():
    with pytest.raises(SystemExit):
        parse_args(["--config", "/nonexistent/uav-api.ini"])


def test_unknown_section_exits(tmp_path):
    config = write_ini(tmp_path, "[apy]\nport = 8001\n")
    with pytest.raises(SystemExit):
        parse_args(["--config", config])


def test_malformed_config_exits(tmp_path):
    config = write_ini(tmp_path, "port = 8001\n")  # key before any section
    with pytest.raises(SystemExit):
        parse_args(["--config", config])


def test_unknown_key_warns_on_system_logger(tmp_path, caplog):
    config = write_ini(tmp_path, "[api]\nprt = 8001\n")
    with caplog.at_level("WARNING", logger="SYSTEM"):
        args = parse_args(["--config", config])
    assert args.port == 8000  # typo'd key ignored, default kept
    assert any("prt" in record.message for record in caplog.records)


# --- config file happy paths ---

def test_simulated_section_presence_enables_simulation(tmp_path):
    config = write_ini(tmp_path, "[simulated]\nspeedup = 5\n")
    args = parse_args(["--config", config])
    assert args.simulated is True
    assert args.speedup == "5"


def test_explicit_simulated_false_overrides_section_presence(tmp_path):
    config = write_ini(tmp_path, "[simulated]\nsimulated = false\n")
    args = parse_args(["--config", config])
    assert args.simulated is False


def test_bad_bool_value_raises(tmp_path):
    config = write_ini(tmp_path, "[simulated]\nsimulated = maybe\n")
    with pytest.raises(ValueError):
        parse_args(["--config", config])


def test_gs_connection_list_parsing(tmp_path):
    config = write_ini(tmp_path, "[simulated]\ngs_connection = [10.0.0.1:14550, 10.0.0.2:14550]\n")
    args = parse_args(["--config", config])
    assert args.gs_connection == ["10.0.0.1:14550", "10.0.0.2:14550"]


def test_empty_gs_connection_list_stays_empty(tmp_path):
    config = write_ini(tmp_path, "[simulated]\ngs_connection = []\n")
    args = parse_args(["--config", config])
    assert args.gs_connection == []


# --- --connection_type choices (#21) ---

@pytest.mark.parametrize("value", ["udpin", "udpout", "usb", "tcp"])
def test_connection_type_accepts_known_values(value):
    assert parse_args(["--connection_type", value]).connection_type == value


def test_connection_type_rejects_unknown_value():
    with pytest.raises(SystemExit):
        parse_args(["--connection_type", "serial"])


# --- --mavlink_streamrate ---

def test_streamrate_default_matches_vehicle_default():
    # The CLI default must not drift from the one Vehicle falls back to.
    import inspect
    from uav_api.vehicles.vehicle import Vehicle
    vehicle_default = inspect.signature(Vehicle.__init__).parameters["default_stream_rate"].default
    assert parse_args([]).mavlink_streamrate == vehicle_default == 5


def test_streamrate_cli_value_is_int():
    assert parse_args(["--mavlink_streamrate", "10"]).mavlink_streamrate == 10


@pytest.mark.parametrize("value", ["0", "-1", "fast"])
def test_streamrate_rejects_non_positive_or_non_int(value):
    with pytest.raises(SystemExit):
        parse_args(["--mavlink_streamrate", value])


def test_streamrate_from_config_arrives_as_string(tmp_path):
    # Config values bypass argparse's type; init_copter/init_plane int() them.
    config = write_ini(tmp_path, "[api]\nmavlink_streamrate = 30\n")
    assert parse_args(["--config", config]).mavlink_streamrate == "30"
