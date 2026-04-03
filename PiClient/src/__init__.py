
import asyncio
from loguru import logger
import sys
from src.open_challenge import run
import argparse

logger.remove()
fmt = (
    "<blue>[{time:HH:mm:ss:SSS}]</blue> │ "
    "<cyan>{line:03}: {function: <18}</cyan> │ "
    "<level>{level: <8}</level> │ "
    "<level>{message}</level>")
logger.add(sys.stderr, level="WARNING", format=fmt)
logger.add("logs/log.txt", level="WARNING", enqueue=True, rotation="5 MB", retention="10 days", format=fmt)

parser = argparse.ArgumentParser(description="Run the main control loop for the robot.")

group = parser.add_mutually_exclusive_group(required=False)
group.add_argument("--verbose", action="store_true", help="Enable verbose logging to verbose.txt")
group.add_argument("--debug", action="store_true", help="Enable debug logging to verbose.txt (overrides --verbose)")

parser.add_argument(
    "--test", 
    nargs="?", # Optional
    const="all", # Empty = "all"
    choices=["camera", "vision", "rpc", "all"], 
    help="Run specific tests (default: all)"
)

parsed_args = parser.parse_args()
if parsed_args.verbose:
    logger.add("logs/verbose.txt", level="INFO", enqueue=True, rotation="1 MB", retention="3 days", format=fmt)
elif parsed_args.debug:
    logger.add("logs/verbose.txt", level="DEBUG", enqueue=True, rotation="1 MB", retention="3 days", format=fmt)


def test_main():
    try:       
        if parsed_args.test == "camera":
            from tests.camera import run_tests as camera_tests
            asyncio.run(camera_tests())
        elif parsed_args.test == "vision":
            from tests.vision import run_tests as vision_tests
            asyncio.run(vision_tests())
        elif parsed_args.test == "rpc":
            from tests.RPC import run_tests as rpc_tests
            asyncio.run(rpc_tests())
        elif parsed_args.test == "all":
            from tests.vision import run_tests as vision_tests
            from tests.camera import run_tests as camera_tests
            from tests.RPC import run_tests as rpc_tests
            # Create a new event loop for maximum isolation, multiprocessing + async + threading all together is not fun
            asyncio.run(camera_tests())
            asyncio.run(vision_tests())
            asyncio.run(rpc_tests())
        else:
            raise ValueError("Invalid test option. Use --test, --test camera, --test vision, --test rpc, or --test all.")

        
        logger.success("All tests completed successfully!")
    except AssertionError as e:
        logger.critical(f"Test failed: {e}")
        logger.info("Test failed with an assertion error, not an runtime exception. Perhaps check your typing or add type annotations michael -_-")
        logger.exception("Traceback:") # Re-raise to be caught by main's exception handler
    

def main():
    try:
        if parsed_args.test:
            test_main()
        else:
            asyncio.run(run())
        exitcode = 0
    except KeyboardInterrupt:
        logger.error("Process Interrupted by User")
        exitcode = 0
    except Exception:
        logger.critical("A FATAL EXCEPTION HAS OCCURED")
        logger.exception("Traceback:")
        exitcode = 1
    finally:
        logger.info(f"Cleaning up with exitcode {exitcode}...")
        logger.remove()
        sys.exit(exitcode)

if __name__ == "__main__":
    main()
else:
    logger.warning("Use `python -m src` to run this module directly. Importing it will not execute the main function, and using the run function directly is not recommended.")
    sys.exit(1)