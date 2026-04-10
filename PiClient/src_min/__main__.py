
import sys
import argparse
from .open_challenge import run
from . import configure_logging, logger


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
        run()
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
