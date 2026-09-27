"""Unit tests for `uav-api setup-sitl`. subprocess.run is replaced by a
recorder, HOME points at tmp_path, and nothing is cloned or built."""

import os

import pytest

from uav_api import setup_sitl
from uav_api.args import parse_setup_sitl_args
from uav_api.setup_sitl import SetupError


@pytest.fixture
def home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SHELL", "/bin/bash")
    return home


@pytest.fixture
def calls(monkeypatch):
    recorded = []

    def fake_run(cmd, cwd=None, env=None, check=False):
        recorded.append({"cmd": cmd, "cwd": cwd, "env": env})

    monkeypatch.setattr(setup_sitl.subprocess, "run", fake_run)
    return recorded


@pytest.fixture
def no_tools(monkeypatch):
    """git present, sim_vehicle.py / xterm / tmux absent; not root; not Debian."""
    monkeypatch.setattr(setup_sitl.shutil, "which", lambda name: "/usr/bin/git" if name == "git" else None)
    monkeypatch.setattr(setup_sitl.os, "geteuid", lambda: 1000, raising=False)
    monkeypatch.setattr(setup_sitl, "_read_os_release", lambda path="/etc/os-release": {"ID": "arch"})


def make_checkout(path, binaries=("arducopter", "arduplane")):
    autotest = path / "Tools" / "autotest"
    autotest.mkdir(parents=True)
    (autotest / "sim_vehicle.py").write_text("")
    bin_dir = path / "build" / "sitl" / "bin"
    bin_dir.mkdir(parents=True)
    for name in binaries:
        (bin_dir / name).write_text("")
    return path


def run(raw_args):
    setup_sitl.run_setup_sitl(parse_setup_sitl_args(raw_args))


# --- preflight ---

def test_root_is_refused(monkeypatch, home, calls, no_tools):
    monkeypatch.setattr(setup_sitl.os, "geteuid", lambda: 0, raising=False)
    with pytest.raises(SetupError, match="root"):
        run(["--ardupilot_path", str(home / "ardupilot")])
    assert calls == []


# --- clone ---

def test_missing_path_is_cloned(home, calls, no_tools):
    target = home / "ardupilot"
    # The fake clone doesn't create the tree, so skip the steps that need it.
    with pytest.raises(SetupError, match="missing"):
        run(["--ardupilot_path", str(target), "--branch", "Copter-4.5"])
    clone = calls[0]["cmd"]
    assert clone[:2] == ["git", "clone"]
    assert "--recurse-submodules" in clone
    assert clone[clone.index("--branch") + 1] == "Copter-4.5"
    assert clone[-1] == str(target)


def test_existing_checkout_updates_submodules(home, calls, no_tools):
    target = make_checkout(home / "ardupilot")
    run(["--ardupilot_path", str(target)])
    assert calls[0]["cmd"] == ["git", "submodule", "update", "--init", "--recursive"]
    assert calls[0]["cwd"] == str(target)
    assert not any(c["cmd"][:2] == ["git", "clone"] for c in calls)


def test_foreign_directory_is_refused(home, calls, no_tools):
    target = home / "something_else"
    target.mkdir()
    with pytest.raises(SetupError, match="not an ArduPilot checkout"):
        run(["--ardupilot_path", str(target)])
    assert calls == []


# --- prereqs ---

def test_prereqs_skipped_on_non_debian(home, calls, no_tools):
    target = make_checkout(home / "ardupilot")
    run(["--ardupilot_path", str(target)])
    assert not any("install-prereqs" in " ".join(c["cmd"]) for c in calls)


def test_prereqs_run_on_ubuntu(monkeypatch, home, calls, no_tools):
    monkeypatch.setattr(setup_sitl.sys, "platform", "linux")
    monkeypatch.setattr(setup_sitl, "_read_os_release",
                        lambda path="/etc/os-release": {"ID": "pop", "ID_LIKE": "ubuntu debian"})
    target = make_checkout(home / "ardupilot")
    run(["--ardupilot_path", str(target)])
    prereqs = [c for c in calls if c["cmd"][0].endswith("install-prereqs-ubuntu.sh")]
    assert len(prereqs) == 1
    assert prereqs[0]["cmd"][1:] == ["-y"]


def test_skip_prereqs(monkeypatch, home, calls, no_tools):
    monkeypatch.setattr(setup_sitl, "_read_os_release", lambda path="/etc/os-release": {"ID": "ubuntu"})
    target = make_checkout(home / "ardupilot")
    run(["--ardupilot_path", str(target), "--skip_prereqs"])
    assert not any("install-prereqs" in " ".join(c["cmd"]) for c in calls)


# --- build ---

def waf_calls(calls):
    return [c["cmd"] for c in calls if c["cmd"][0] == "./waf"]


def test_build_targets_follow_vehicle(home, calls, no_tools):
    target = make_checkout(home / "ardupilot", binaries=("arduplane",))
    run(["--ardupilot_path", str(target), "--vehicle", "plane"])
    assert waf_calls(calls) == [["./waf", "configure", "--board", "sitl"], ["./waf", "plane"]]


def test_build_defaults_to_both(home, calls, no_tools):
    target = make_checkout(home / "ardupilot")
    run(["--ardupilot_path", str(target)])
    assert waf_calls(calls)[1:] == [["./waf", "copter"], ["./waf", "plane"]]


def test_skip_build_tolerates_missing_binaries(home, calls, no_tools):
    target = make_checkout(home / "ardupilot", binaries=())
    run(["--ardupilot_path", str(target), "--skip_build"])
    assert waf_calls(calls) == []


def test_missing_binary_after_build_fails(home, calls, no_tools):
    target = make_checkout(home / "ardupilot", binaries=("arducopter",))
    with pytest.raises(SetupError, match="arduplane"):
        run(["--ardupilot_path", str(target)])


def test_ardupilot_venv_prepended_to_path(home, calls, no_tools):
    (home / "venv-ardupilot" / "bin").mkdir(parents=True)
    target = make_checkout(home / "ardupilot")
    run(["--ardupilot_path", str(target)])
    env = next(c["env"] for c in calls if c["cmd"][0] == "./waf")
    assert env["PATH"].split(os.pathsep)[0] == str(home / "venv-ardupilot" / "bin")


def test_failed_step_raises_setup_error(monkeypatch, home, no_tools):
    def failing_run(cmd, cwd=None, env=None, check=False):
        raise setup_sitl.subprocess.CalledProcessError(2, cmd)

    monkeypatch.setattr(setup_sitl.subprocess, "run", failing_run)
    target = make_checkout(home / "ardupilot")
    with pytest.raises(SetupError, match="status 2"):
        run(["--ardupilot_path", str(target)])


# --- PATH registration ---

def test_path_line_appended_once(home, calls, no_tools):
    target = make_checkout(home / "ardupilot")
    run(["--ardupilot_path", str(target)])
    run(["--ardupilot_path", str(target)])
    bashrc = (home / ".bashrc").read_text()
    assert bashrc.count(f"export PATH=$PATH:{target}/Tools/autotest") == 1


def test_path_already_registered_with_home_var(home, calls, no_tools):
    (home / ".bashrc").write_text("export PATH=$PATH:$HOME/ardupilot/Tools/autotest\n")
    target = make_checkout(home / "ardupilot")
    run(["--ardupilot_path", str(target)])
    assert "uav-api setup-sitl" not in (home / ".bashrc").read_text()


def test_zsh_uses_zshrc(monkeypatch, home, calls, no_tools):
    monkeypatch.setenv("SHELL", "/usr/bin/zsh")
    target = make_checkout(home / "ardupilot")
    run(["--ardupilot_path", str(target)])
    assert (home / ".zshrc").exists()
    assert not (home / ".bashrc").exists()


def test_no_path_leaves_rc_alone(home, calls, no_tools):
    target = make_checkout(home / "ardupilot")
    run(["--ardupilot_path", str(target), "--no_path"])
    assert not (home / ".bashrc").exists()


# --- locations ---

def test_locations_registered(home, calls, no_tools):
    target = make_checkout(home / "ardupilot")
    run(["--ardupilot_path", str(target), "--skip_build"])
    locations = (home / ".config" / "ardupilot" / "locations.txt").read_text()
    assert "AbraDF=" in locations
