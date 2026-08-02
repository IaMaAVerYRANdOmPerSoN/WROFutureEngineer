"""Pi Client - Main robot control package.

This package provides the core logging configuration and module-level imports for the WRO Future Engineer robot.
"""

from typing import Literal, TYPE_CHECKING

import sys
from loguru import logger
if TYPE_CHECKING:
    from loguru import Record

from . import *
from . import lib  # Because pyright is stupid and doesn't understand * imports


def format_fn(record: "Record") -> str:
    location = record["file"].name + ":" + str(record["line"])
    return (
        "<blue>{elapsed.seconds}.{elapsed.microseconds:06d}</blue> | "
        f"<cyan>{location: <25}</cyan> | "
        "<level>{level: <8}</level> | "
        "<level>{message}</level>"
        f"{'{extra}' if record['extra'] else ''}\n"
        f"{'{exception}' if record['exception'] else ''}"
    )


# Logging configuration before configure_logging() is called; ensures consistent formatting.
logger.remove()
logger.add(
    "logs/log.txt",
    level="WARNING",
    enqueue=True,
    rotation="5 MB",
    retention="10 days",
    backtrace=True,
    diagnose=True,
    format=format_fn,
    colorize=True,
)
logger.add(sys.stderr, level="WARNING", backtrace=True,
           diagnose=True, format=format_fn)


def configure_logging(level: Literal["CRITICAL", "ERROR", "WARNING", "SUCCESS", "INFO", "DEBUG"]) -> None:
    """Configure shared logging sinks for the Pi client package."""
    logger.remove()
    logger.add(
        "logs/log.txt",
        level=level,
        enqueue=True,
        rotation="5 MB",
        retention="10 days",
        backtrace=True,
        diagnose=True,
        format=format_fn,
        colorize=True,
    )
    logger.add(sys.stderr, level=level, backtrace=True,
               diagnose=True, format=format_fn, colorize=True)

    if level == "DEBUG":
        logger.add(
            "logs/verbose.txt",
            level="DEBUG",
            enqueue=True,
            rotation="1 MB",
            retention="3 days",
            backtrace=True,
            diagnose=True,
            format=format_fn,
            colorize=True,
        )
    elif level == "INFO":
        logger.add(
            "logs/verbose.txt",
            level="INFO",
            enqueue=True,
            rotation="1 MB",
            retention="3 days",
            backtrace=True,
            diagnose=True,
            format=format_fn,
            colorize=True,
        )


lib.export_globals()
