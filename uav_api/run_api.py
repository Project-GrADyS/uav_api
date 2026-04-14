import subprocess
import sys

from uav_api.args import parse_args, write_args_to_env
from uav_api.setup import setup
from uav_api.log import _build_hypercorn_log_config

def run_with_args(raw_args=None):
    args = parse_args(raw_args)
    args = setup(args)
    write_args_to_env(args)

    if args.udp:
        log_config_path = _build_hypercorn_log_config(args)
        cmd = [
            sys.executable, "-m", "hypercorn",
            "uav_api.api_app:app",
            "--quic-bind", f"0.0.0.0:{args.port}",
            "--certfile", args.certfile,
            "--keyfile", args.keyfile,
            "--access-logfile", "-",
            "--error-logfile", "-",
            "--log-config", f"json:{log_config_path}",
            "--reload",
        ]
    else:
        cmd = [
            sys.executable, "-m", "uvicorn",
            "uav_api.api_app:app",
            "--host", "0.0.0.0",
            "--port", str(args.port),
            "--log-level", "debug",
            "--reload",
        ]

    process = subprocess.Popen(cmd)

    print("API process created.")

    return process

def main():
    api_process = run_with_args()
    try:
        api_process.wait()
    except KeyboardInterrupt:
        api_process.terminate()
        api_process.wait()  # Wait for the process to actually terminate
        print("UAV API process terminated.")

if __name__ == "__main__":
    main()
