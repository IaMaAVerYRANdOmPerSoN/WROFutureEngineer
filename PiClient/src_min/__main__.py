
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
        const="all",  # Empty = "all"
        choices=["camera", "vision", "rpc", "all"],
        help="Run specific tests (default: all)",
    )

    return parser.parse_args()


def test_main(test_target: str):
    try:       
        if test_target == "camera":
            from tests.camera import run_tests as camera_tests
            camera_tests()
        elif test_target == "vision":
            from tests.vision import run_tests as vision_tests
            vision_tests()
        elif test_target == "rpc":
            from tests.RPC import run_tests as rpc_tests
            rpc_tests()
        elif test_target == "all":
            from tests.vision import run_tests as vision_tests
            from tests.camera import run_tests as camera_tests
            from tests.RPC import run_tests as rpc_tests
            camera_tests()
            vision_tests()
            rpc_tests()
        else:
            raise ValueError("Invalid test option. Use --test, --test camera, --test vision, --test rpc, or --test all.")

        
        logger.success("All tests completed successfully!")
    except AssertionError as e:
        logger.critical(f"Test failed: {e}")
        logger.info("Test failed with an assertion error, not an runtime exception. Perhaps check your typing or add type annotations michael -_-")
        logger.exception("Traceback:") # Re-raise to be caught by main's exception handler
    

def main():
    parsed_args = parse_args()
    configure_logging(verbose=parsed_args.verbose, debug=parsed_args.debug)

    try:
        if parsed_args.test:
            test_main(parsed_args.test)
        else:
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
