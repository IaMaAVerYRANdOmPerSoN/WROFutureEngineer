
"""Pi Client entry point.

Parses command-line arguments and dispatches to the selected challenge
loop (open or obstacle). Supports --verbose and --debug logging flags.
"""

import asyncio
import sys
from .core.open_challenge import run_open_challenge
from .core.obstacle_challenge import run_obstacle_challenge
import argparse
from . import configure_logging, logger


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the Pi Client.

    :returns: Parsed namespace with ``--verbose``, ``--debug``, and ``--challenge`` options.
    :rtype: argparse.Namespace
    """
    parser = argparse.ArgumentParser(
        description="Run the main control loop for the robot.")

    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--verbose", action="store_true",
                       help="Enable verbose logging to verbose.txt")
    group.add_argument("--debug", action="store_true",
                       help="Enable debug logging to verbose.txt (overrides --verbose)")

    parser.add_argument(
        "--challenge",
        choices=["open", "obstacle"],
        default="open",
        help="Select which challenge loop to run (default: open).",
    )

    return parser.parse_args()


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


if __name__ == "__main__":
    main()
