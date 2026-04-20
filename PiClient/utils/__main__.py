import asyncio

from utils import logger, configure_logging
import argparse
import sys

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
        choices=["raw", "contours", "contourbinary", "LiDAR", "control", "config"],
        help="Select which tool(s) to run (can specify multiple, e.g., --tool raw contours control).",
    )

    return parser.parse_args()

def main():
    args = parse_args()
    configure_logging(verbose=args.verbose, debug=args.debug)

    if not args.tool:
        logger.error("No tool specified. Use --tool to select at least one tool.")
        sys.exit(1)

    for tool in args.tool:
        # Each tool should open in a separate window, so we can run multiple at once
        if tool == "raw":
            from tools.raw import run_raw_tool
            asyncio.create_task(run_raw_tool())
        elif tool == "contours":
            from tools.contours import run_contours_tool
            run_contours_tool()
        elif tool == "contourbinary":
            from tools.contourbinary import run_contourbinary_tool
            run_contourbinary_tool()
        elif tool == "LiDAR":
            from tools.lidar import run_lidar_tool
            run_lidar_tool()
        elif tool == "control":
            from tools.control import run_control_tool
            run_control_tool()
        elif tool == "config":
            from tools.config import run_config_tool
            run_config_tool()