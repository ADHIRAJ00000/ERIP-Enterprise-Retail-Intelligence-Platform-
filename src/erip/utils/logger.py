"""
Logging utility for ERIP.
Provides a consistent, configured logger across every module so pipeline
runs produce traceable, production-style logs (console + rotating file).
"""

import logging
import logging.handlers
import sys
from pathlib import Path

from erip.config.settings import LOG_FORMAT, LOG_LEVEL, LOGS_DIR


def get_logger(name: str, log_file: str = "erip_pipeline.log") -> logging.Logger:
    """
    Return a configured logger.

    Args:
        name: Usually __name__ of the calling module.
        log_file: File under LOGS_DIR to append to (rotated at 5MB, 5 backups).

    Returns:
        A logging.Logger instance with console + rotating file handlers attached.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        # Already configured (avoid duplicate handlers on repeated imports)
        return logger

    logger.setLevel(LOG_LEVEL)
    formatter = logging.Formatter(LOG_FORMAT)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    file_path = Path(LOGS_DIR) / log_file
    file_handler = logging.handlers.RotatingFileHandler(
        file_path, maxBytes=5 * 1024 * 1024, backupCount=5
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.propagate = False
    return logger
