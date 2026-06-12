"""Utilities package for tuning and debugging tools.

Provides shared logging, OpenCV access, and the tool launcher entry point.
"""

import sys
from loguru import logger
import cv2

LOG_FORMAT = (
    "<blue>[{time:HH:mm:ss:SSS}]</blue> | "
    "<cyan>{line:03}: {function: <18}</cyan> | "
    "<level>{level: <8}</level> | "
    "<level>{message}</level>"
)
"""str: Default loguru format string with coloured time, line, function, and level fields."""

def configure_logging(verbose: bool = False, debug: bool = False) -> None:
    """Configure shared logging sinks for the Pi client package."""
    logger.remove()
    logger.add(
        "logs/log.txt",
        level="WARNING",
        enqueue=True,
        rotation="5 MB",
        retention="10 days",
        format=LOG_FORMAT,
    )

    if debug:
        logger.add(
            "logs/verbose.txt",
            level="DEBUG",
            enqueue=True,
            rotation="1 MB",
            retention="3 days",
            format=LOG_FORMAT,
        )
        logger.add(sys.stderr, level="DEBUG", format=LOG_FORMAT)
    elif verbose:
        logger.add(
            "logs/verbose.txt",
            level="INFO",
            enqueue=True,
            rotation="1 MB",
            retention="3 days",
            format=LOG_FORMAT,
        )
        logger.add(sys.stderr, level="INFO", format=LOG_FORMAT)
    else:
        logger.add(sys.stderr, level="WARNING", format=LOG_FORMAT)

__all__ = ["configure_logging", "logger", "cv2"]