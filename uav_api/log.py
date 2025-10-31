import logging
import os

def set_log_config(args):

    log_config_logger = logging.getLogger("LOG_CONFIG")
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
        }
    }

    if "COPTER" in args.log_console:
        logging_config['loggers']["COPTER"]['handlers'].append('console_handler')
    if "API" in args.log_console:
        logging_config['loggers']["uvicorn"]['handlers'].append('console_handler')
        logging_config['loggers']["uvicorn.access"]['handlers'].append('console_handler')
        logging_config['loggers']["uvicorn.error"]['handlers'].append('console_handler')

    if "COPTER" in args.log_console:
        logging_config['loggers']["COPTER"]['level'] = "DEBUG"
    if "API" in args.log_console:
        logging_config['loggers']["uvicorn"]['level'] = "DEBUG"
        logging_config['loggers']["uvicorn.access"]['level'] = "DEBUG"
        logging_config['loggers']["uvicorn.error"]['level'] = "DEBUG"

    logging.config.dictConfig(logging_config)