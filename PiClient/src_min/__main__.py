
import sys
import argparse
from . import configure_logging
from . import logger
from .open_challenge import run_open_challenge
from .obstacle_challenge import run_obstacle_challenge


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the main control loop for the robot.")

    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--verbose", action="store_true", help="Enable verbose logging to verbose.txt")
    group.add_argument("--debug", action="store_true", help="Enable debug logging to verbose.txt (overrides --verbose)")

    parser.add_argument(
        "--test",
        nargs="?",  # Optional
        help="Not supported in the minimal version."
    )
    parser.add_argument(
        "--challenge",
        choices=["open", "obstacle"],
        default="open",
        help="Select which challenge loop to run (default: open).",
    )

    return parser.parse_args()


def test_main(test_target: str):
    if test_target:
        logger.warning("Testing mode is not supported in the minimal version. Ignoring --test argument.")
    

def main():
    parsed_args = parse_args()
    configure_logging(verbose=parsed_args.verbose, debug=parsed_args.debug)

    try:
        if parsed_args.test:
            logger.warning("Testing mode is not supported in the minimal version. Ignoring --test argument.")
        if parsed_args.challenge == "obstacle":
            run_obstacle_challenge()
        else:
            run_open_challenge()
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
