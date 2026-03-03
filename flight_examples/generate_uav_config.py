import argparse
import configparser
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Generate a per-UAV config file from the real_drone_with_gradys_gs template."
    )
    parser.add_argument("sysid", type=int, help="MAVLink system ID for the UAV")
    args = parser.parse_args()

    config = configparser.ConfigParser()
    config["api"] = {
        "port": str(8000 + args.sysid),
        "uav_connection": "127.0.0.1:17171",
        "connection_type": "udpin",
        "sysid": str(args.sysid),
        "gradys_gs": "127.0.0.1:8000",
    }

    output_path = Path("/etc/uavs/default.ini")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        config.write(f)

    print(f"Generated {output_path}")


if __name__ == "__main__":
    main()
