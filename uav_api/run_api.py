import subprocess

from uav_api.args import parse_args, write_args_to_env

def run_with_args(raw_args=None):
    args = parse_args(raw_args)
    write_args_to_env(args)
    
    process = subprocess.Popen([
        "python", "-m", "uvicorn",
        "uav_api.api_app:app",
        "--host", "0.0.0.0",
        "--port", str(args.port),
        "--log-level", "debug",
        "--reload"
    ])

    print("API process created.")

    return process

if __name__ == "__main__":
    api_process = run_with_args()
    api_process.wait()
