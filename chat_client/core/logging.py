import logging
import os
from pathlib import Path
from data.config import DATA_DIR
from concurrent_log_handler import ConcurrentRotatingFileHandler
import typing

logger: logging.Logger = logging.getLogger(__name__)

# 100 MB per log file
# 5 backup files
MAX_LOG_SIZE = 100 * 1024 * 1024
BACKUP_COUNT = 5

formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")


def get_rotating_file_handler(level: typing.Any, file_name):
    Path(file_name).touch()
    handler = ConcurrentRotatingFileHandler(file_name, maxBytes=MAX_LOG_SIZE, backupCount=BACKUP_COUNT)
    handler.setLevel(level)
    handler.setFormatter(formatter)
    return handler


# check if data dir exists and create it if not
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)


def setup_logging(log_level: int = logging.INFO):
    """
    Configures the logging setup with the specified log level.
    """

    logger = logging.getLogger()
    logger.setLevel(log_level)
    logger.propagate = False

    # Remove existing handlers
    while logger.handlers:
        logger.handlers.pop()

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # Rotating File Handler
    log_file = Path(DATA_DIR) / "main.log"
    rotating_file_handler = get_rotating_file_handler(log_level, log_file)
    logger.addHandler(rotating_file_handler)

    logger.debug("Logging setup complete. Log level: %s", log_level)
