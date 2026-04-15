import logging
import logging.config

def build_hypercorn_log_config(args):
    """Build a logging dictConfig dict for Hypercorn loggers.

    Returns the dict to be passed directly to Config.logconfig_dict.
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
        'loggers': {
            'hypercorn.access': {
                'level': 'INFO',
                'handlers': [],
                'propagate': False
            },
            'hypercorn.error': {
                'level': 'INFO',
                'handlers': []
            },
        }
    }

    if args.log_path:
        logging_config['handlers']['file_handler'] = {
            'class': 'logging.FileHandler',
            'filename': args.log_path,
            'formatter': 'file_formatter'
        }
        for logger in logging_config['loggers'].values():
            logger['handlers'].append('file_handler')

    if "API" in args.log_console:
        logging_config['loggers']['hypercorn.access']['handlers'].append('console_handler')
        logging_config['loggers']['hypercorn.error']['handlers'].append('console_handler')

    if "API" in args.debug:
        logging_config['loggers']['hypercorn.access']['level'] = "DEBUG"
        logging_config['loggers']['hypercorn.error']['level'] = "DEBUG"

    return logging_config

def set_log_config(args):
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
        "handlers": {
            'console_handler': {
                'class': 'logging.StreamHandler',
                'formatter': 'console_formatter'
            },
        },
        'loggers': {
            'COPTER': {
                'level': 'INFO',
                'handlers': []
            },
            "uvicorn": {
                'level': 'INFO',
                'handlers': []
            },
            "uvicorn.access": {
                'level': 'INFO',
                'handlers': []
            },
            "uvicorn.error": {
                'level': 'INFO',
                'handlers': []
            },
            "GRADYS_GS": {
                'level': 'INFO',
                'handlers': []
            }
        }
    }

    if args.log_path:
        logging_config['handlers']['file_handler'] = {
            'class': 'logging.FileHandler',
            'filename': args.log_path,
            'formatter': 'file_formatter'
        }
        for logger in logging_config['loggers'].values():
            logger['handlers'].append('file_handler')

    if "COPTER" in args.log_console:
        logging_config['loggers']["COPTER"]['handlers'].append('console_handler')
    if "API" in args.log_console:
        logging_config['loggers']["uvicorn"]['handlers'].append('console_handler')
        logging_config['loggers']["uvicorn.access"]['handlers'].append('console_handler')
        logging_config['loggers']["uvicorn.error"]['handlers'].append('console_handler')
    if "GRADYS_GS" in args.log_console:
        logging_config['loggers']["GRADYS_GS"]['handlers'].append('console_handler')

    if "COPTER" in args.debug:
        logging_config['loggers']["COPTER"]['level'] = "DEBUG"
    if "API" in args.debug:
        logging_config['loggers']["uvicorn"]['level'] = "DEBUG"
        logging_config['loggers']["uvicorn.access"]['level'] = "DEBUG"
        logging_config['loggers']["uvicorn.error"]['level'] = "DEBUG"
    if "GRADYS_GS" in args.debug:
        logging_config['loggers']["GRADYS_GS"]['level'] = "DEBUG"

    logging.config.dictConfig(logging_config)
