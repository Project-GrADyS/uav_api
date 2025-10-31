import os

def ensure_home_subdir_exists(subdir_name):
    home_dir = os.path.expanduser("~")  # Gets the home directory path
    target_path = os.path.join(home_dir, subdir_name)

    if not os.path.exists(target_path):
        os.makedirs(target_path)
        print(f"Created directory: {target_path}")
    else:
        print(f"Directory already exists: {target_path}")

def ensure_home_file_exists(filename, content=""):
    home_dir = os.path.expanduser("~")  # Gets the user's home directory
    file_path = os.path.join(home_dir, filename)

    if not os.path.isfile(file_path):
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"Created file: {file_path}")
    else:
        print(f"File already exists: {file_path}")

def setup(args):

    locations = "AbraDF=-15.840081,-47.926642,1042,30\nAbradf1=-15.8427104,-47.9231787,1042,30\nAbradf2=-15.8415750,-47.9290581,1042,30\nAbradf3=-15.8436186,-47.9262686,1042,30"

    ensure_home_subdir_exists(".config/ardupilot")
    ensure_home_file_exists(".config/ardupilot/locations.txt", locations)

    if args.log_path is None:
        ensure_home_subdir_exists("uav_api_logs")
        ensure_home_subdir_exists("uav_api_logs/uav_logs")
        ensure_home_file_exists(f"uav_api_logs/uav_logs/uav_{args.sysid}.log")
        if args.simulated:
            ensure_home_subdir_exists("uav_api_logs/ardupilot_logs")

        home_dir = os.path.expanduser("~")  # Gets the user's home directory
        args.log_path = os.path.join(home_dir, "uav_api_logs","uav_logs",f"uav_{args.sysid}.log")
    return args