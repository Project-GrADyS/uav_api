import multiprocessing
import uvicorn

from uav_api.args import parse_args, write_args_to_env
from uav_api.setup import setup
from uav_api.log import build_hypercorn_log_config

def run_with_args(raw_args=None):
    """Parse args, configure, and start the ASGI server (blocking)."""
    args = parse_args(raw_args)
    args = setup(args)
    write_args_to_env(args)

    if args.udp:
        from hypercorn.config import Config
        from hypercorn.run import run as hypercorn_run

        log_config = build_hypercorn_log_config(args)

        config = Config()
        config.application_path = "uav_api.api_app:app"
        config.bind = [f"0.0.0.0:{args.port}"]
        config.quic_bind = [f"0.0.0.0:{args.port}"]
        config.certfile = args.certfile
        config.keyfile = args.keyfile
        config.accesslog = "-"
        config.errorlog = "-"
        config.logconfig_dict = log_config

        hypercorn_run(config)
    else:
        uvicorn.run(
            "uav_api.api_app:app",
            host="0.0.0.0",
            port=args.port,
            log_level="debug",
        )

def spawn_with_args(raw_args=None):
    """Start the ASGI server in a separate process (non-blocking).

    Returns a multiprocessing.Process that can be joined or terminated.
    Used by integration tests that need the server running in the background.
    """
    process = multiprocessing.Process(target=run_with_args, args=(raw_args,))
    process.start()
    return process

def main():
    try:
        run_with_args()
    except KeyboardInterrupt:
        print("UAV API process terminated.")

if __name__ == "__main__":
    main()
