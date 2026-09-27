
import configparser
import json
import argparse
import logging
import os
import sys

# Section names accepted in config files, mirroring the five argument groups
# below (parse_mode, parse_api, parse_logs, parse_simulated, parse_udp).
KNOWN_SECTIONS = {"mode", "api", "logs", "simulated", "udp"}

def namespace_to_str(namespace: argparse.Namespace) -> str:
    """Convert argparse.Namespace to a JSON string."""
    return json.dumps(vars(namespace))

def str_to_namespace(s: str) -> argparse.Namespace:
    """Convert JSON string back to argparse.Namespace."""
    data = json.loads(s)
    return argparse.Namespace(**data)

def write_args_to_env(args):
    os.environ['UAV_ARGS'] = namespace_to_str(args)

def read_args_from_env() -> argparse.Namespace:
    """Read UAV_ARGS from environment variable and convert it back to argparse.Namespace."""
    args_str = os.getenv('UAV_ARGS')
    if args_str:
        return str_to_namespace(args_str)
    return None

_TRUE_VALUES = {"true", "yes", "on", "1"}
_FALSE_VALUES = {"false", "no", "off", "0"}

def coerce_bool(key, value):
    """Read a config-file value as a boolean.

    Config values arrive as strings, so an uncoerced `headless = false` would be
    the truthy string "false" and silently turn the option ON. An unrecognised
    value raises rather than falling back to truthiness: a service refusing to
    start beats a vehicle running in a mode nobody asked for.
    """
    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ValueError(
        f"Invalid boolean for '{key}': {value!r}. Use one of "
        f"{sorted(_TRUE_VALUES)} or {sorted(_FALSE_VALUES)}."
    )

def parse_args(raw_args=None):
    parser = argparse.ArgumentParser(
        prog="uav-api start",
        description="Welcome to the UAV Runner, this script runs an API that interfaces with Ardupilots instances (real or simulated)."
    )
    parse_mode(parser)
    parse_api(parser)
    parse_logs(parser)
    parse_simulated(parser)
    parse_udp(parser)
    args = parser.parse_args(raw_args)

    if args.config:
        config = configparser.ConfigParser()
        try:
            read_files = config.read(args.config)
        except configparser.Error as e:
            parser.error(f"Malformed config file {args.config}: {e}")
        # configparser treats a missing or unreadable path as "nothing to
        # read", which on a real drone presents as "API up, no MAVLink".
        if not read_files:
            parser.error(f"Config file not found or unreadable: {args.config}")

        unknown_sections = sorted(set(config.sections()) - KNOWN_SECTIONS)
        if unknown_sections:
            parser.error(
                f"Unknown section(s) {unknown_sections} in {args.config}; "
                f"known sections: {sorted(KNOWN_SECTIONS)}"
            )

        if "simulated" in config.sections():
            setattr(args, "simulated", True)

        for section in config.sections():
            for key, value in config.items(section):
                if hasattr(args, key):
                    # An argument whose parsed default is a bool is a boolean
                    # argument -- no hardcoded list of names to keep in step.
                    # This runs after the `[simulated]` rule above, so an
                    # explicit `simulated = false` key overrides it.
                    if isinstance(getattr(args, key), bool):
                        value = coerce_bool(key, value)
                    elif value.startswith("["):
                        # Drop empty entries: "[]".strip("[]") is "", and
                        # "".split(",") is [""] -- never an empty list. Without
                        # this filter, `gs_connection=[]` yields [""], which
                        # becomes a dangling `--out ` in the SITL command line.
                        value = [v.strip() for v in value.strip("[]").split(",") if v.strip()]
                    setattr(args, key, value)
                else:
                    logging.getLogger("SYSTEM").warning(
                        f"Config key '{key}' in [{section}] of {args.config} "
                        "does not match any argument; ignored"
                    )
    return args
    
COMMANDS = {
    "start": "Run the API (real drone, or SITL with --simulated). Default when no command is given.",
    "setup-sitl": "Install ArduPilot SITL: clone, install prerequisites, build, register PATH and locations.",
}

def top_level_help():
    lines = [
        "usage: uav-api [start|setup-sitl] [options]",
        "",
        "HTTP interface for MAVLink commands on ArduPilot vehicles.",
        "",
        "commands:",
    ]
    lines += [f"  {name:<12}{text}" for name, text in COMMANDS.items()]
    lines += [
        "",
        "With no command, the options are passed to 'start', so 'uav-api --config x.ini'",
        "is the same as 'uav-api start --config x.ini'.",
        "Run 'uav-api <command> --help' for the options of each command.",
    ]
    return "\n".join(lines)

def split_command(argv):
    """Split argv into (command, remaining args).

    A bare invocation (no command word) is an alias for `start`: deployed
    systemd units and scripts run `uav-api --config ...` and must keep working.
    """
    if argv and argv[0] in COMMANDS:
        return argv[0], argv[1:]
    if argv and argv[0] in ("-h", "--help"):
        print(top_level_help())
        raise SystemExit(0)
    if argv and not argv[0].startswith("-"):
        print(top_level_help(), file=sys.stderr)
        raise SystemExit(f"uav-api: unknown command '{argv[0]}'")
    return "start", argv

def parse_setup_sitl_args(raw_args=None):
    parser = argparse.ArgumentParser(
        prog="uav-api setup-sitl",
        description="Install ArduPilot SITL so 'uav-api start --simulated' can run: "
                    "clone ArduPilot, install its prerequisites, build the SITL "
                    "binaries, put sim_vehicle.py on PATH and register uav_api's "
                    "SITL locations. Safe to re-run."
    )

    parser.add_argument(
        '--ardupilot_path',
        dest='ardupilot_path',
        default="~/ardupilot",
        help="Where the ArduPilot checkout lives. Cloned there if the directory does not exist; "
             "an existing ArduPilot checkout is reused."
    )

    parser.add_argument(
        '--branch',
        dest='branch',
        default=None,
        help="Branch or tag to clone (e.g. Copter-4.5). Defaults to ArduPilot's default branch. "
             "Ignored when the checkout already exists."
    )

    parser.add_argument(
        '--vehicle',
        dest='vehicle',
        choices=['copter', 'plane'],
        nargs='+',
        default=['copter', 'plane'],
        help="Which SITL binaries to build (default: both)."
    )

    parser.add_argument(
        '--skip_prereqs',
        dest='skip_prereqs',
        action='store_true',
        default=False,
        help="Do not run ArduPilot's install-prereqs script (it uses sudo and apt)."
    )

    parser.add_argument(
        '--skip_build',
        dest='skip_build',
        action='store_true',
        default=False,
        help="Do not build the SITL binaries."
    )

    parser.add_argument(
        '--no_path',
        dest='no_path',
        action='store_true',
        default=False,
        help="Do not add Tools/autotest to PATH in your shell rc file; "
             "pass --ardupilot_path to 'uav-api start' instead."
    )

    return parser.parse_args(raw_args)

# MODE PARSER
def parse_mode(mode_parser):

    mode_parser.add_argument(
        '--simulated',
        dest='simulated',
        action='store_true',
        default=False,
        help="Simulate the vehicle using Ardupilot's SITL (bare flag; presence enables simulation)"
    )

    mode_parser.add_argument(
        '--config',
        dest='config',
        default=None,
        help="Configuration file for UAV execution"
    )

    mode_parser.add_argument(
        '--root_dir',
        dest='root_dir',
        default="~/.uav_api",
        help="Root directory for all runtime artifacts (logs/, scripts/, certs/). "
             "Individual path arguments override their derived defaults."
    )

    mode_parser.add_argument(
        '--vehicle',
        dest='vehicle',
        choices=['copter', 'plane'],
        default='copter',
        help="Vehicle type. Selects which routers are registered and which ArduPilot SITL binary spawns."
    )

# API PARSER
def parse_api(api_parser):

    api_parser.add_argument(
        '--port',
        dest='port',
        type=int,
        default=8000,
        help='Port for api to run on'
    )

    api_parser.add_argument(
        '--uav_connection',
        dest='uav_connection',
        default='127.0.0.1:17171',
        help='Address used for copter connection'
    )

    api_parser.add_argument(
        '--connection_type',
        dest='connection_type',
        default='udpin',
        choices=['udpin', 'udpout', 'usb', 'tcp'],
        help="Connection scheme for the vehicle link. udpin/udpout/tcp prefix "
             "uav_connection as '<type>:<address>'; usb passes uav_connection "
             "through raw as a serial device path (e.g. /dev/ttyACM0)"
    )

    api_parser.add_argument(
        '--sysid',
        dest='sysid',
        type=int,
        default=10,
        help='Sysid for Copter'
    )

    api_parser.add_argument(
        '--gradys_gs',
        dest='gradys_gs',
        type=str,
        default=None,
        help='Address for Gradys Ground Station connection'
    )

    api_parser.add_argument(
        '--scripts_path',
        dest='scripts_path',
        type=str,
        default=None,
        help='Directory for uploaded mission scripts (default: <root_dir>/scripts)'
    )

    api_parser.add_argument(
        '--python_path',
        dest='python_path',
        type=str,
        default="python3",
        help='Path for python binary to use when executing scripts'
    )
# SIMULATED PARSER
def parse_simulated(simulated_parser):

    simulated_parser.add_argument(
        '--location',
        dest='location',
        default="AbraDF",
        help="""Location name for UAV home. To register a new location name run the following command:
            bash scripts/registry_location [LOCATION_NAME] [GPS_LAT] [GPS_LONG] [GPS_ALT] [HEADING]
        """
    )

    simulated_parser.add_argument(
        '--gs_connection',
        dest='gs_connection',
        default=[],
        help="Address for GroundStation connection",
        nargs='*'
    )

    simulated_parser.add_argument(
        '--speedup',
        dest='speedup',
        type=int,
        default=1,
        help="Multiplication factor for simulation time."
    )

    simulated_parser.add_argument(
        '--ardupilot_path',
        dest='ardupilot_path',
        default=None,
        help="Path for ardupilot repository. If omitted, sim_vehicle.py is resolved from the PATH environment variable."
    )

    simulated_parser.add_argument(
        '--terminal',
        dest='terminal',
        default='xterm -e',
        help="Terminal command used to wrap SITL, following ArduPilot's "
             "SITL_RITW_TERMINAL convention (e.g. 'xterm -e', "
             "'gnome-terminal --'). Ignored with --headless."
    )

    simulated_parser.add_argument(
        '--headless',
        dest='headless',
        action='store_true',
        default=False,
        help="Run SITL without opening any terminal window, for hosts with no X server. "
             "SITL output goes to <root_dir>/logs/ardupilot_logs/sitl_<sysid>.log"
    )

def parse_logs(logs_parser):

    # Defines which values are accepted as a LOGGER input.
    def valid_loggers_type(value):
        valid_loggers = {'UVICORN', 'VEHICLE', 'GRADYS_GS', 'SCRIPT'}
        if value not in valid_loggers:
            raise argparse.ArgumentTypeError('Invalid value. Please choose one of the following: value1, value2, or both')
        return value
    
    logs_parser.add_argument(
        "--log_console",
        dest="log_console",
        default=[],
        type=valid_loggers_type,
        help="List of loggers to be handled in console. This loggers need to be a subset of: COPTER, PROTOCOL and API.",
        nargs='*'
    )

    logs_parser.add_argument(
        "--log_path",
        dest="log_path",
        default=None,
        help="Saves log files to the provided path (default: <root_dir>/logs/uav_logs/uav_<sysid>.log). This log file will receive the logs from all loggers of that UAV. Which include: COPTER, GRADYS_GS and API."
    )

    logs_parser.add_argument(
        "--debug",
        dest="debug",
        default=[],
        type=valid_loggers_type,
        help="Which loggers to apply debug level. Possible logger: COPTER, PROTOCOL and API.",
        nargs="*"
    )

    logs_parser.add_argument(
        "--script_logs",
        dest="script_logs",
        default=None,
        help="Saves script executed by mission route out and err files to the provided path (default: <root_dir>/logs/script_logs)"
    )

def parse_udp(udp_parser):

    udp_parser.add_argument(
        '--udp',
        dest='udp',
        action='store_true',
        default=False,
        help='Use Hypercorn with QUIC/HTTP3 (UDP) instead of Uvicorn (TCP)'
    )

    udp_parser.add_argument(
        '--certfile',
        dest='certfile',
        default=None,
        help='Path to TLS certificate PEM file (for --udp mode). Auto-generated under <root_dir>/certs if omitted.'
    )

    udp_parser.add_argument(
        '--keyfile',
        dest='keyfile',
        default=None,
        help='Path to TLS private key PEM file (for --udp mode). Auto-generated under <root_dir>/certs if omitted.'
    )