import logging
import logging.config
import os


def resolve_log_file(log_path):
    """Expand a configured log path and make sure its directory exists.

    Both callers below hand this straight to `logging.FileHandler`, which opens
    the file eagerly at `dictConfig` time -- a missing parent directory aborts
    startup with `ValueError: Unable to configure handler`. The fix has to live
    here rather than in `setup()`, because `run_api.run_with_args` configures
    logging *before* it calls `setup()`.

    Also expands `~`: nothing else in the codebase does, so an INI written with
    `log_path = ~/uav_api_logs/...` would otherwise resolve to a literal `./~`
    directory even when the real one exists.
    """
    resolved = os.path.expanduser(log_path)
    parent = os.path.dirname(os.path.abspath(resolved))
    os.makedirs(parent, exist_ok=True)
    return resolved


def _build_log_config(args, token_loggers, always_console=(), no_propagate=()):
    """Build a logging dictConfig dict.

    token_loggers maps each --log_console/--debug token (e.g. "UVICORN") to the
    logger names it controls, so the same wiring serves both ASGI servers --
    only the logger names differ between uvicorn and hypercorn. Loggers in
    always_console get the console handler unconditionally; loggers in
    no_propagate get 'propagate': False.
    """
    logging_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'console_formatter': {
                'format': f"[%(name)s-{args.sysid}] %(levelname)s - %(message)s"
            },
            'file_formatter': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            }
        },
        'handlers': {
            'console_handler': {
                'class': 'logging.StreamHandler',
                'formatter': 'console_formatter'
            },
        },
        'loggers': {}
    }

    for names in token_loggers.values():
        for name in names:
            logger = {'level': 'INFO', 'handlers': []}
            if name in no_propagate:
                logger['propagate'] = False
            logging_config['loggers'][name] = logger
    for name in always_console:
        logging_config['loggers'][name] = {'level': 'INFO', 'handlers': ['console_handler']}

    if args.log_path:
        logging_config['handlers']['file_handler'] = {
            'class': 'logging.FileHandler',
            'filename': resolve_log_file(args.log_path),
            'formatter': 'file_formatter'
        }
        for logger in logging_config['loggers'].values():
            logger['handlers'].append('file_handler')

    for token, names in token_loggers.items():
        if token in args.log_console:
            for name in names:
                logging_config['loggers'][name]['handlers'].append('console_handler')
        if token in args.debug:
            for name in names:
                logging_config['loggers'][name]['level'] = "DEBUG"

    return logging_config


def build_hypercorn_log_config(args):
    """Build a logging dictConfig dict for Hypercorn loggers.

    Returns the dict to be passed directly to Config.logconfig_dict.
    """
    return _build_log_config(
        args,
        {"UVICORN": ["hypercorn.access", "hypercorn.error"]},
        no_propagate=("hypercorn.access",),
    )


def set_log_config(args):
    vehicle_logger = "PLANE" if args.vehicle == "plane" else "COPTER"
    token_loggers = {
        "VEHICLE": [vehicle_logger],
        "UVICORN": ["uvicorn", "uvicorn.access", "uvicorn.error"],
        "GRADYS_GS": ["GRADYS_GS"],
        "SCRIPT": ["SCRIPT"],
    }
    logging.config.dictConfig(
        _build_log_config(args, token_loggers, always_console=("SYSTEM",))
    )
