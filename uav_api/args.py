
import configparser
import json
import argparse
import os
import ast

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

def parse_config_file(file_path):
    config = configparser.ConfigParser()
    config.read(file_path)
    print(config.sections())

def parse_args(raw_args=None):
    parser = argparse.ArgumentParser(description="Welcome to the UAV Runner, this script runs an API that interfaces with Ardupilots instances (real or simulated).")
    parse_mode(parser)
    parse_api(parser)
    parse_logs(parser)
    parse_simulated(parser)
    args = parser.parse_args(raw_args)

    if args.config:
        #parse_config_file(args.config)
        config = configparser.ConfigParser()
        config.read(args.config)

        if "simulated" in config.sections():
            setattr(args, "simulated", True)

        for section in config.sections():
            for key, value in config.items(section):
                if hasattr(args, key):
                    if value[0] == "[":
                        value = value.strip("[]").split(",")
                        value = [v.strip() for v in value]
                    setattr(args, key, value)
                else:
                    print(f"Warning: {key} not found in args")
    return args
    
# MODE PARSER
def parse_mode(mode_parser):

    mode_parser.add_argument(
        '--simulated',
        dest='simulated',
        type=bool,
        default=False,
        help="Wheter to simulate copter using Ardupilot's SITL or not"
    )

    mode_parser.add_argument(
        '--config',
        dest='config',
        default=None,
        help="Configuration file for UAV execution"
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
        help="Connection type (client or server) for copter. Either udpin or udpout"
    )

    api_parser.add_argument(
        '--sysid',
        dest='sysid',
        type=int,
        default=10,
        help='Sysid for Copter'
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
        default='~/ardupilot',
        help="Path for ardupilot repository"
    )

def parse_logs(logs_parser):

    # Defines which values are accepted as a LOGGER input.
    def valid_loggers_type(value):
        valid_loggers = {'API', 'COPTER'}
        if not value in valid_loggers:
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
        help="If provided, saves log files to path. This log file will receive the logs from all loggers of that UAV. Which include: COPTER, PROTOCOL and API."
    )

    logs_parser.add_argument(
        "--debug",
        dest="debug",
        default=[],
        type=valid_loggers_type,
        help="Which loggers to apply debug level. Possible logger: COPTER, PROTOCOL and API.",
        nargs="*"
    )