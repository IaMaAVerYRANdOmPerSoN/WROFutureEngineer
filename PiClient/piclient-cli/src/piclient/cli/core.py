"""CLI entry point for the WRO Future Engineer robot.

Provides the ``main()`` function wired to the ``wro`` console script
(``pip install piclient[cli]``) and the ``__main__`` module for
``python -m piclient.cli``.
"""

import asyncio
import sys
import argparse
from .piclient_argument_parser import PICLIENT_ARGUMENT_PARSER
import dataclasses

from typing import NoReturn

from piclient.open_challenge import run_open_challenge
# pyright: ignore[reportMissingTypeStubs]
from piclient.obstacle_challenge import run_obstacle_challenge # pyright: ignore[reportMissingTypeStubs]
from piclient.core import configure_logging, logger
from piclient.core.lib import export, GLOBAL_CONFIG

from collections.abc import Generator


def _set_nested_attr(root: object, dotted_path: str, value: object) -> None:
    """Set ``root.a.b.c = value`` given ``dotted_path == 'a.b.c'``."""
    *parents, leaf = dotted_path.split(".")
    for part in parents:
        root = getattr(root, part)
    setattr(root, leaf, value)


def _walk_config(
    obj: object,
    prefix: str = "",
) -> Generator[tuple[str, object], None, None]:
    """Yield ``(dotted_key, value)`` pairs for every leaf in a nested dataclass tree."""
    for key, value in vars(obj).items():
        full_key = f"{prefix}.{key}" if prefix else key
        if dataclasses.is_dataclass(value):
            yield from _walk_config(value, full_key)
        else:
            yield full_key, value


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the challenges.

    :returns: Parsed namespace.
    """
    parser = PICLIENT_ARGUMENT_PARSER()

    for k, v in _walk_config(GLOBAL_CONFIG()):
        parser.add_argument(f"--{k}", help=f"Default: {v}")

    return parser.parse_args()


@export
def main() -> NoReturn:
    """Main entry point for the Pi Client.

    Configures logging, selects the challenge based on CLI arguments,
    and runs the appropriate async challenge loop. Handles graceful
    shutdown on KeyboardInterrupt and logs fatal exceptions.
    """
    parsed_args: argparse.Namespace = _parse_args()
    configure_logging(getattr(parsed_args, "GeneralConfig.LEVEL", "WARNING"))

    for key, value in vars(parsed_args).items():
        _set_nested_attr(GLOBAL_CONFIG(), key, value)

    exitcode = 1
    try:
        if getattr(parsed_args, "GeneralConfig.CHALLENGE", "open") == "obstacle":
            asyncio.run(main=run_obstacle_challenge())
        elif getattr(parsed_args, "GeneralConfig.CHALLENGE", "open") == "open":
            asyncio.run(main=run_open_challenge())
        else:
            logger.warning("Nothing to run!")
        exitcode = 0
    except KeyboardInterrupt:
        logger.error(
            "SIGINT recieved, shutting down... (Send SIGINT [CTRL+C] again to force)")
        exitcode = 0
    except Exception:
        logger.critical("A FATAL EXCEPTION HAS OCCURRED")
        logger.exception("Traceback:")
        exitcode = 1
    finally:
        logger.info(f"Cleaning up with exitcode {exitcode}...")
        logger.remove()
        sys.exit(exitcode)
