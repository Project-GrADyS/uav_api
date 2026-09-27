"""`uav-api setup-sitl`: take a machine from nothing to a working ArduPilot SITL.

Every step is idempotent, so re-running after a failure (or on an already
set-up machine) only does what is still missing.
"""
import logging
import os
import shutil
import subprocess
import sys

from uav_api.args import parse_setup_sitl_args
from uav_api.setup import CUSTOM_LOCATIONS, _resolve_home_path, merge_locations

logger = logging.getLogger("SYSTEM")

ARDUPILOT_REPO = "https://github.com/ArduPilot/ardupilot.git"
SITL_SETUP_URL = "https://ardupilot.org/dev/docs/SITL-setup-landingpage.html"
PREREQS_SCRIPT = "Tools/environment_install/install-prereqs-ubuntu.sh"
# Created by install-prereqs-ubuntu.sh on releases whose system Python is
# externally managed (Ubuntu 23.04+). It is activated from ~/.bashrc, so it is
# not active in this process yet.
ARDUPILOT_VENV = "~/venv-ardupilot"

WAF_TARGETS = {"copter": "copter", "plane": "plane"}
SITL_BINARIES = {"copter": "arducopter", "plane": "arduplane"}

class SetupError(Exception):
    pass

def _run(step, cmd, cwd=None, env=None):
    """Run a command with inherited stdio so the user sees output and sudo prompts."""
    logger.info(f"[{step}] $ {' '.join(cmd)}")
    try:
        subprocess.run(cmd, cwd=cwd, env=env, check=True)
    except FileNotFoundError as e:
        raise SetupError(f"{step}: command not found: {e.filename}") from e
    except subprocess.CalledProcessError as e:
        raise SetupError(f"{step}: '{' '.join(cmd)}' exited with status {e.returncode}") from e

def _is_ardupilot_checkout(path):
    return os.path.isfile(os.path.join(path, "Tools", "autotest", "sim_vehicle.py"))

def preflight():
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        raise SetupError(
            "Do not run setup-sitl as root: ArduPilot's prerequisites script refuses "
            "root and the checkout would land in root's home. Run it as your user; "
            "it calls sudo where needed."
        )
    if shutil.which("git") is None:
        raise SetupError("git is not installed; install it and re-run setup-sitl.")

def ensure_checkout(path, branch):
    if not os.path.exists(path):
        cmd = ["git", "clone", "--recurse-submodules"]
        if branch:
            cmd += ["--branch", branch]
        cmd += [ARDUPILOT_REPO, path]
        _run("clone", cmd)
        return
    if not _is_ardupilot_checkout(path):
        raise SetupError(
            f"{path} exists but is not an ArduPilot checkout "
            "(no Tools/autotest/sim_vehicle.py). Pass a different --ardupilot_path."
        )
    logger.info(f"[clone] Reusing existing ArduPilot checkout at {path}")
    if branch:
        logger.warning(f"[clone] --branch {branch} ignored: the checkout already exists")
    _run("clone", ["git", "submodule", "update", "--init", "--recursive"], cwd=path)

def _read_os_release(path="/etc/os-release"):
    info = {}
    try:
        with open(path) as f:
            for line in f:
                if "=" in line:
                    key, value = line.rstrip("\n").split("=", 1)
                    info[key] = value.strip('"')
    except OSError:
        pass
    return info

def is_debian_like(os_release):
    ids = {os_release.get("ID", "")} | set(os_release.get("ID_LIKE", "").split())
    return bool(ids & {"ubuntu", "debian"})

def install_prereqs(path, os_release_path="/etc/os-release"):
    if not sys.platform.startswith("linux") or not is_debian_like(_read_os_release(os_release_path)):
        logger.warning(
            "[prereqs] Automatic prerequisite install only supports Debian/Ubuntu. "
            f"Install ArduPilot's prerequisites by hand ({SITL_SETUP_URL}), then "
            "re-run with --skip_prereqs."
        )
        return
    _run("prereqs", [os.path.join(path, PREREQS_SCRIPT), "-y"], cwd=path)

def build_env():
    """Environment for waf: the ArduPilot venv first on PATH when it exists."""
    env = os.environ.copy()
    venv_bin = os.path.join(os.path.expanduser(ARDUPILOT_VENV), "bin")
    if os.path.isdir(venv_bin):
        env["PATH"] = venv_bin + os.pathsep + env.get("PATH", "")
    return env

def build(path, vehicles):
    env = build_env()
    _run("build", ["./waf", "configure", "--board", "sitl"], cwd=path, env=env)
    for vehicle in vehicles:
        _run("build", ["./waf", WAF_TARGETS[vehicle]], cwd=path, env=env)

def shell_rc_file():
    shell = os.path.basename(os.environ.get("SHELL", ""))
    return _resolve_home_path(".zshrc" if shell == "zsh" else ".bashrc")

def register_path(path):
    """Put Tools/autotest on PATH via the shell rc file. Returns the rc file touched, if any."""
    autotest = os.path.join(path, "Tools", "autotest")

    resolved = shutil.which("sim_vehicle.py")
    if resolved and os.path.realpath(os.path.dirname(resolved)) == os.path.realpath(autotest):
        logger.info("[path] sim_vehicle.py already resolves to this checkout")
        return None

    rc_file = shell_rc_file()
    existing = ""
    if os.path.isfile(rc_file):
        with open(rc_file) as f:
            existing = f.read()
    # install-prereqs-ubuntu.sh writes this line itself, spelled either with
    # the absolute path or with $HOME.
    home = os.path.expanduser("~")
    spellings = {autotest}
    if autotest.startswith(home):
        spellings.add("$HOME" + autotest[len(home):])
    if any(s in existing for s in spellings):
        logger.info(f"[path] {autotest} already registered in {rc_file}")
        return rc_file

    with open(rc_file, "a") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        f.write(f"# Added by uav-api setup-sitl\nexport PATH=$PATH:{autotest}\n")
    logger.info(f"[path] Added {autotest} to PATH in {rc_file}")
    return rc_file

def register_locations():
    merge_locations(_resolve_home_path(".config/ardupilot/locations.txt"), CUSTOM_LOCATIONS)
    logger.info("[locations] uav_api SITL locations registered")

def verify(path, vehicles, skip_build):
    missing = []
    for vehicle in vehicles:
        binary = os.path.join(path, "build", "sitl", "bin", SITL_BINARIES[vehicle])
        if not os.path.isfile(binary):
            missing.append(binary)
    if missing and not skip_build:
        raise SetupError(f"Build finished but SITL binaries are missing: {missing}")
    for binary in missing:
        logger.warning(f"[verify] {binary} not built yet; sim_vehicle.py will build it on first start")
    if shutil.which("xterm") is None:
        logger.warning("[verify] xterm not found: install it, or start SITL with --headless")
    if shutil.which("tmux") is None:
        logger.warning("[verify] tmux not found: mission scripts (/mission/execute-script) need it")

def run_setup_sitl(args):
    path = os.path.abspath(os.path.expanduser(args.ardupilot_path))

    preflight()
    ensure_checkout(path, args.branch)
    if not args.skip_prereqs:
        install_prereqs(path)
    if not args.skip_build:
        build(path, args.vehicle)
    rc_file = None if args.no_path else register_path(path)
    register_locations()
    verify(path, args.vehicle, args.skip_build)

    vehicle_flag = "" if "copter" in args.vehicle else " --vehicle plane"
    if args.no_path:
        next_cmd = f"uav-api start --simulated --ardupilot_path {path}{vehicle_flag}"
    elif rc_file:
        next_cmd = f"source {rc_file} && uav-api start --simulated{vehicle_flag}"
    else:
        next_cmd = f"uav-api start --simulated{vehicle_flag}"
    logger.info(f"SITL setup complete. Next: {next_cmd}")

def main(raw_args=None):
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = parse_setup_sitl_args(raw_args)
    try:
        run_setup_sitl(args)
    except SetupError as e:
        logger.error(f"setup-sitl failed: {e}")
        raise SystemExit(1)
