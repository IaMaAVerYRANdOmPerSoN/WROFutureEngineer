import asyncio
from utils import cv2, logger, configure_logging
import argparse
import sys
import multiprocessing as mp
from multiprocessing import shared_memory


def parse_args():
    parser = argparse.ArgumentParser(
        description="Tune color thresholds, ROIs, view detections and control loop outputs, and tune configuration parameters for the Pi client.")

    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--verbose", action="store_true",
                       help="Enable verbose logging to verbose.txt")
    group.add_argument("--debug", action="store_true",
                       help="Enable debug logging to verbose.txt (overrides --verbose)")

    parser.add_argument(
        "--tool", "-t",
        nargs="+",  # Mandatory
        choices=["raw", "contours", "contourbinary",
                 "LiDAR", "control"],
        help="Select which tool(s) to run (can specify multiple, e.g., --tool raw contours control).",
    )

    return parser.parse_args()


async def main():
    args = parse_args()
    configure_logging(verbose=args.verbose, debug=args.debug)

    if not args.tool:
        logger.error(
            "No tool specified. Use --tool to select at least one tool.")
        sys.exit(1)

    futures = []
    for tool in args.tool:
        # Each tool should open in a separate window, so we can run multiple at once
        if tool == "raw":
            from utils.tools.raw import run_raw_tool
            futures.append(asyncio.create_task(run_raw_tool()))
        elif tool == "contours":
            from utils.tools.contours import run_contours_tool
            futures.append(asyncio.create_task(run_contours_tool()))
        elif tool == "contourbinary":
            from utils.tools.contour_binary import run_contourbinary_tool
            futures.append(asyncio.create_task(run_contourbinary_tool()))
        elif tool == "LiDAR":
            from utils.tools.lidar import run_lidar_tool
            futures.append(asyncio.create_task(run_lidar_tool()))
        elif tool == "control":
            from utils.tools.control import run_control_tool
            futures.append(asyncio.create_task(run_control_tool()))

    try:
        await asyncio.gather(*futures)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.error("Program interrupted by user.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        try:
            logger.info("Shutting down tools...")

            cv2.destroyAllWindows()

            for future in futures:
                if not future.done():
                    future.cancel()

            await asyncio.gather(*futures, return_exceptions=True)

            for process in mp.active_children():
                process.terminate()
                process.join(timeout=1)

            # OS cleans up shared memory on process termination (apparently?!)
            # ftr I don't belive that so
            try:
                shared_memory._cleanup() # type: ignore Please don't file 67 issues saying that i'm calling a private method
            except Exception:
                pass

            logger.info("All tools have been shut down.")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
            logger.warning(
                "Some tools may not have shut down cleanly. You may need to close windows or terminate processes manually. Also do rm -rf /dev/shm/* because shared memory")

if __name__ == "__main__":
    asyncio.run(main())
