import logging
import os

def ensure_home_subdir_exists(subdir_name):
    home_dir = os.path.expanduser("~")  # Gets the home directory path
    target_path = os.path.join(home_dir, subdir_name)

    if not os.path.exists(target_path):
        os.makedirs(target_path)
        print(f"Created directory: {target_path}")
    else:
        print(f"Directory already exists: {target_path}")

def ensure_home_file_exists(filename):
    home_dir = os.path.expanduser("~")  # Gets the user's home directory
    file_path = os.path.join(home_dir, filename)

    if not os.path.isfile(file_path):
        with open(file_path, 'w') as f:
            pass  # Creates an empty file
        print(f"Created file: {file_path}")
    else:
        print(f"File already exists: {file_path}")

def set_log_config(args):

    log_config_logger = logging.getLogger("LOG_CONFIG")

    if args.log_path is None:
        ensure_home_subdir_exists("uav_api_logs")
        ensure_home_subdir_exists("uav_api_logs/uav_logs")
        ensure_home_file_exists(f"uav_api_logs/uav_logs/uav_{args.sysid}.log")
        if args.simulated:
            ensure_home_subdir_exists("uav_api_logs/ardupilot_logs")

        home_dir = os.path.expanduser("~")  # Gets the user's home directory
        args.log_path = os.path.join(home_dir, "uav_api_logs","uav_logs",f"uav_{args.sysid}.log")

    # Default log config
    logging_config = {
        'version': 1,
        'formatters': {
            'console_formatter': {
                'format': f"[%(name)s-{args.sysid}] %(levelname)s - %(message)s"
            },
            'file_formatter': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            }
        },
        "handlers": {
            'console_handler': {
                'class': 'logging.StreamHandler',
                'formatter': 'console_formatter'
            },
            'file_handler': {
                'class': 'logging.FileHandler',
                'filename': args.log_path,
                'formatter': 'file_formatter'
            }
        },
        'loggers': {
            'COPTER': {
                'level': 'INFO',
                'handlers': ['file_handler']
            },
            "uvicorn": {
                'level': 'INFO',
                'handlers': ['file_handler']
            },
            "uvicorn.access": {
                'level': 'INFO',
                'handlers': ['file_handler']
            },
            "uvicorn.error": {
                'level': 'INFO',
                'handlers': ['file_handler']
            },
            "API": {
                'level': 'INFO',
                'handlers': ['file_handler', 'console_handler']
            }
        }
    }

    for logger_name in args.log_console:
        if logger_name in logging_config["loggers"]:
            logging_config['loggers'][logger_name]['handlers'].append('console_handler')

    for logger_name in args.debug:
        if logger_name in logging_config["loggers"]:
            logging_config['loggers'][logger_name]['level'] = 'DEBUG'

    logging.config.dictConfig(logging_config)