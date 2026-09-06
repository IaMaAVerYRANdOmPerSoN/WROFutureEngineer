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
    """Format one Loguru record with elapsed time and source location.

    The formatter includes the log level, message, optional contextual extras,
    and optional exception details using Loguru markup.

    :param record: Loguru record mapping containing message and metadata.
    :returns: Markup-formatted line suitable for the configured logger sink.
    :rtype: str
    """
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
    """Configure console and rotating file sinks for the package.

    ``logs/log.txt`` rotates at 5 MB and is retained for 10 days. ``INFO`` and
    ``DEBUG`` additionally create ``logs/verbose.txt`` with 1 MB rotation and
    3-day retention. Existing Loguru sinks are removed first.

    :param level: Minimum Loguru level for the console and standard log file.
    :returns: ``None``.
    :rtype: None
    """
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
