import logging
import sys
import os

def setup_logger(name='person_search', level=None):
    """
    Set up and configure logger for the application

    Args:
        name: Logger name
        level: Logging level (defaults to INFO, DEBUG if FLASK_ENV=development)

    Returns:
        Configured logger instance
    """
    if level is None:
        level = logging.DEBUG if os.getenv('FLASK_ENV') == 'development' else logging.INFO

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.hasHandlers():
        logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(funcName)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)

    return logger
