"""Unit tests for the shared logging-config builder: handler wiring per
--log_console/--debug, file handler iff --log_path, and the hypercorn/uvicorn
logger sets staying in step."""

import argparse

from uav_api.log import _build_log_config, build_hypercorn_log_config


def make_args(**overrides):
    defaults = dict(
        sysid=10, vehicle="copter", log_console=[], debug=[], log_path=None
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


UVICORN_LOGGERS = ["uvicorn", "uvicorn.access", "uvicorn.error"]


def build_main_config(args):
    vehicle_logger = "PLANE" if args.vehicle == "plane" else "COPTER"
    token_loggers = {
        "VEHICLE": [vehicle_logger],
        "UVICORN": UVICORN_LOGGERS,
        "GRADYS_GS": ["GRADYS_GS"],
        "SCRIPT": ["SCRIPT"],
    }
    return _build_log_config(args, token_loggers, always_console=("SYSTEM",))


def test_defaults_console_only_on_system():
    config = build_main_config(make_args())
    assert config["loggers"]["SYSTEM"]["handlers"] == ["console_handler"]
    for name in UVICORN_LOGGERS + ["COPTER", "GRADYS_GS", "SCRIPT"]:
        assert config["loggers"][name]["handlers"] == []
        assert config["loggers"][name]["level"] == "INFO"
    assert "file_handler" not in config["handlers"]


def test_log_path_attaches_file_handler_to_every_logger(tmp_path):
    config = build_main_config(make_args(log_path=str(tmp_path / "uav.log")))
    assert "file_handler" in config["handlers"]
    for logger in config["loggers"].values():
        assert "file_handler" in logger["handlers"]


def test_log_console_and_debug_target_their_token_loggers():
    config = build_main_config(make_args(log_console=["UVICORN"], debug=["VEHICLE"]))
    for name in UVICORN_LOGGERS:
        assert "console_handler" in config["loggers"][name]["handlers"]
        assert config["loggers"][name]["level"] == "INFO"
    assert config["loggers"]["COPTER"]["level"] == "DEBUG"
    assert config["loggers"]["COPTER"]["handlers"] == []


def test_vehicle_token_follows_vehicle_arg():
    config = build_main_config(make_args(vehicle="plane", log_console=["VEHICLE"]))
    assert "console_handler" in config["loggers"]["PLANE"]["handlers"]
    assert "COPTER" not in config["loggers"]


def test_hypercorn_config_mirrors_uvicorn_wiring(tmp_path):
    args = make_args(
        log_console=["UVICORN"], debug=["UVICORN"], log_path=str(tmp_path / "uav.log")
    )
    config = build_hypercorn_log_config(args)
    assert set(config["loggers"]) == {"hypercorn.access", "hypercorn.error"}
    for name, logger in config["loggers"].items():
        assert logger["level"] == "DEBUG"
        assert "console_handler" in logger["handlers"]
        assert "file_handler" in logger["handlers"]
    # run_in_terminal access logs must not double-print through the root logger
    assert config["loggers"]["hypercorn.access"]["propagate"] is False
    assert "propagate" not in config["loggers"]["hypercorn.error"]


def test_hypercorn_config_defaults_are_quiet():
    config = build_hypercorn_log_config(make_args())
    for logger in config["loggers"].values():
        assert logger["handlers"] == []
        assert logger["level"] == "INFO"
