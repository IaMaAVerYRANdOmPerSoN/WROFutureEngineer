"""Entry point for ``python -m piclient.obstacle_challenge``."""

import asyncio
from .runner import run_obstacle_challenge
from piclient.core import configure_logging, logger

if __name__ == "__main__":
    configure_logging(level_ = "WARNING")
    try:
        asyncio.run(run_obstacle_challenge())
    except KeyboardInterrupt:
        logger.error("Process Interrupted by User")
    except Exception:
        logger.critical("A FATAL EXCEPTION HAS OCCURRED")
    finally:
        logger.info("Cleaning up...")
        logger.remove()
