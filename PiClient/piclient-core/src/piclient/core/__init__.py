"""Pi Client - Main robot control package.

This package provides the core logging configuration and module-level imports for the WRO Future Engineer robot.
"""

import sys
from typing import Literal
from loguru import logger
from . import lib  # Shut up pylance
from . import *

LOG_FORMAT = (
    "<blue>[{time:HH:mm:ss:SSS}]</blue> | "
    "<cyan>{line:03}: {function: <18}</cyan> | "
    "<level>{level: <8}</level> | "
    "<level>{message}</level>"
)
"""str: Default loguru format string with coloured time, line, function, and level fields."""


# Logging configuration before configure_logging() is called; ensures consistent formatting.
logger.remove()
logger.add(
    "logs/log.txt",
    level="WARNING",
    enqueue=True,
    rotation="5 MB",
    retention="10 days",
    format=LOG_FORMAT,
)
logger.add(sys.stderr, level="WARNING", format=LOG_FORMAT)


def configure_logging(level: Literal["CRITICAL", "ERROR", "WARNING", "SUCCESS", "INFO", "DEBUG"]) -> None:
    """Configure shared logging sinks for the Pi client package."""
    logger.remove()
    logger.add(
        "logs/log.txt",
        level=level,
        enqueue=True,
        rotation="5 MB",
        retention="10 days",
        format=LOG_FORMAT,
    )
    logger.add(sys.stderr, level=level, format=LOG_FORMAT)

    if level == "DEBUG":
        logger.add(
            "logs/verbose.txt",
            level="DEBUG",
            enqueue=True,
            rotation="1 MB",
            retention="3 days",
            format=LOG_FORMAT,
        )
    elif level == "INFO":
        logger.add(
            "logs/verbose.txt",
            level="INFO",
            enqueue=True,
            rotation="1 MB",
            retention="3 days",
            format=LOG_FORMAT,
        )


lib.export_globals()
