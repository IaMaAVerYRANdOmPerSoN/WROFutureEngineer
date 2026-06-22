"""CLI entry point for the WRO Future Engineer robot.

Provides the ``main()`` function wired to the ``wro`` console script
(``pip install piclient[cli]``) and the ``__main__`` module for
``python -m piclient.cli``.
"""

import asyncio
import sys
import argparse

from piclient.open_challenge import run_open_challenge
from piclient.obstacle_challenge import run_obstacle_challenge
from piclient.core import configure_logging, logger
from piclient.core.lib import export


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the challenges.

    :returns: Parsed namespace with ``--verbose``, ``--debug``, and ``--challenge`` options.
    """
    parser = argparse.ArgumentParser(
        description="Run the main control loop for the robot.")
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("-v", "--verbose", action="store_true",
                       help="Enable verbose logging to verbose.txt")
    group.add_argument("-d", "--debug", action="store_true",
                       help="Enable debug logging to verbose.txt (overrides --verbose)")
    parser.add_argument(
        "-c",
        "--challenge",
        choices=["open", "obstacle"],
        default="open",
        help="Select which challenge loop to run (default: open).",
    )
    return parser.parse_args()


@export
def main():
    """Main entry point for the Pi Client.

    Configures logging, selects the challenge based on CLI arguments,
    and runs the appropriate async challenge loop. Handles graceful
    shutdown on KeyboardInterrupt and logs fatal exceptions.
    """
    parsed_args = _parse_args()
    configure_logging(verbose=parsed_args.verbose, debug=parsed_args.debug)

    try:
        if parsed_args.challenge == "obstacle":
            asyncio.run(run_obstacle_challenge())
        elif parsed_args.challenge == "open":
            asyncio.run(run_open_challenge())
        else:
            logger.warning("Nothing to run!")
        exitcode = 0
    except KeyboardInterrupt:
        logger.error("Process Interrupted by User")
        exitcode = 0
    except Exception:
        logger.critical("A FATAL EXCEPTION HAS OCCURRED")
        logger.exception("Traceback:")
        exitcode = 1
    finally:
        logger.info(f"Cleaning up with exitcode {exitcode}...")
        logger.remove()
        sys.exit(exitcode)
