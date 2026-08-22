"""Unit tests for root_dir path derivation. Uses parse_args + derive_paths
directly (not setup(), which also writes ArduPilot's locations.txt under the
real home directory)."""

import os

from uav_api.args import parse_args
from uav_api.setup import ardupilot_logs_dir, derive_paths, ensure_dev_certs


def test_defaults_derive_from_default_root():
    args = derive_paths(parse_args(["--sysid", "7"]))
    root = os.path.abspath(os.path.expanduser("~/.uav_api"))
    assert args.root_dir == root
    assert args.log_path == os.path.join(root, "logs", "uav_logs", "uav_7.log")
    assert args.script_logs == os.path.join(root, "logs", "script_logs")
    assert args.scripts_path == os.path.join(root, "scripts")
    assert ardupilot_logs_dir(args) == os.path.join(root, "logs", "ardupilot_logs")


def test_root_dir_relocates_everything(tmp_path):
    args = derive_paths(parse_args(["--root_dir", str(tmp_path / "state")]))
    root = str(tmp_path / "state")
    assert args.root_dir == root
    for path in (args.log_path, args.script_logs, args.scripts_path,
                 ardupilot_logs_dir(args)):
        assert path.startswith(root + os.sep)


def test_explicit_paths_override_derivation(tmp_path):
    args = derive_paths(parse_args([
        "--root_dir", str(tmp_path / "state"),
        "--log_path", str(tmp_path / "elsewhere" / "api.log"),
        "--scripts_path", str(tmp_path / "my_scripts"),
        "--script_logs", str(tmp_path / "my_script_logs"),
    ]))
    assert args.log_path == str(tmp_path / "elsewhere" / "api.log")
    assert args.scripts_path == str(tmp_path / "my_scripts")
    assert args.script_logs == str(tmp_path / "my_script_logs")


def test_dev_certs_generate_under_root(tmp_path):
    args = parse_args(["--udp", "--root_dir", str(tmp_path / "state")])
    args = ensure_dev_certs(args)
    certs_dir = str(tmp_path / "state" / "certs")
    assert args.certfile == os.path.join(certs_dir, "dev-cert.pem")
    assert args.keyfile == os.path.join(certs_dir, "dev-key.pem")
    assert os.path.isfile(args.certfile)
    assert os.path.isfile(args.keyfile)


def test_explicit_certfile_skips_generation(tmp_path):
    args = parse_args([
        "--udp", "--root_dir", str(tmp_path / "state"),
        "--certfile", "/etc/ssl/uav.pem", "--keyfile", "/etc/ssl/uav.key",
    ])
    args = ensure_dev_certs(args)
    assert args.certfile == "/etc/ssl/uav.pem"
    assert not os.path.exists(tmp_path / "state" / "certs")
