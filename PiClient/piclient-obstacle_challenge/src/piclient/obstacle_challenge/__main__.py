"""Entry point for ``python -m piclient.obstacle_challenge``."""

import asyncio
from loguru import logger
from piclient.core import configure_logging
from .runner import run_obstacle_challenge

if __name__ == "__main__":
    configure_logging(level="WARNING")
    try:
        asyncio.run(run_obstacle_challenge())
    except KeyboardInterrupt:
        logger.error("Process Interrupted by User")
    except Exception:
        logger.critical("A FATAL EXCEPTION HAS OCCURRED", exc_info=True)
    finally:
        logger.info("Cleaning up...")
        logger.remove()
