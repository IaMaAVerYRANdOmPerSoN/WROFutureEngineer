"""CLI entry point for the WRO Future Engineer robot.

Provides the ``main()`` function wired to the ``wro`` console script
(``pip install piclient[cli]``) and the ``__main__`` module for
``python -m piclient.cli``.
"""

from typing import NoReturn

import argparse
import asyncio
import os
import sys

from loguru import logger

from piclient.core import configure_logging
from piclient.core.lib import export, GLOBAL_CONFIG
from piclient.obstacle_challenge import run_obstacle_challenge
from piclient.open_challenge import run_open_challenge

from .argument_parser import TypedArgumentParser


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the challenges.

    :returns: Parsed namespace.
    """
    return TypedArgumentParser(GLOBAL_CONFIG()).parse_args()


async def _init_sentry() -> None:
    """
    Initialize Sentry SDK for error tracking if SENTRY_DSN is set in the environment.

    "In async programs, we recommend to initialize the
    Sentry SDK inside an async function to ensure async
    code is instrumented properly. If possible, call
    sentry_sdk.init() at the beginning of the first
    async function you call" --- sentry sdk docs
    """
    dsn: str | None = os.getenv("SENTRY_DSN")
    if not dsn:
        return

    try:
        import sentry_sdk
    except ImportError:
        return

    sentry_sdk.init(
        dsn=dsn,
        send_default_pii=True,
        traces_sample_rate=1.0,  # Everything, until everything is working
        enable_logs=True,
    )


@export
def main() -> NoReturn:
    """Main entry point for the Pi Client.

    Configures logging, selects the challenge based on CLI arguments,
    and runs the appropriate async challenge loop. Handles graceful
    shutdown on KeyboardInterrupt and logs fatal exceptions.
    """
    asyncio.run(_init_sentry())

    try:
        GLOBAL_CONFIG().from_toml()
    except OSError:
        logger.warning(
            "No configuration file found, using cli args, env vars, and defaults")
    GLOBAL_CONFIG().from_env()

    parsed_args: argparse.Namespace = _parse_args()
    configure_logging(getattr(parsed_args, "GeneralConfig.LEVEL", "WARNING"))

    GLOBAL_CONFIG().freeze()  # Prevent further modifications to the configuration

    exitcode = 1
    try:
        with logger.catch(reraise=True):
            if getattr(parsed_args, "GeneralConfig.CHALLENGE", "open") == "obstacle":
                asyncio.run(run_obstacle_challenge())
            elif getattr(parsed_args, "GeneralConfig.CHALLENGE", "open") == "open":
                asyncio.run(run_open_challenge())
            else:
                logger.warning("Nothing to run!")
            exitcode = 0
    except KeyboardInterrupt:
        logger.error("SIGINT received, shutting down... (Send SIGINT [CTRL+C] again to force)")
        exitcode = 0
    except Exception:
        logger.critical("Robot Crashed Unexpectedly (See above for Traceback)")
        exitcode = 1
        raise
    finally:
        logger.info(f"Cleaning up with exitcode {exitcode}...")
        logger.remove()
        sys.exit(exitcode)
