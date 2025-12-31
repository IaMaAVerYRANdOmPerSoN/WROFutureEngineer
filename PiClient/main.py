import asyncio
import sys
from loguru import logger
from commProtocol import Client
from visionProcessing import AsyncVisionProcessor
from asyncCamera import AsyncCamera

logger.remove()
fmt = (
    "<blue>[{time:HH:mm:ss:SSS}]</blue> │ "
    "<cyan>{line:03}: {function: <18}</cyan> │ "
    "<level>{level: <8}</level> │ "
    "<level>{message}</level>")
logger.add(sys.stderr, level="WARNING", format=fmt)
logger.add("log.txt", level="WARNING", enqueue=True, rotation="5 MB", retention="10 days", format=fmt)
logger.add("verbose.txt", level="DEBUG", enqueue=True, rotation="1 MB", retention="3 days", format=fmt, backtrace=True, diagnose=True)

async def main():
    async with Client() as client, AsyncVisionProcessor() as vision, AsyncCamera() as camera:

        # Starting code here
        state = "Follow wall"

        async for frame in camera.stream():
            futures = (
                vision.check_field_bonds(frame),
                vision.find_walls(frame),
                vision.find_obstacles(frame),
                vision.check_corner_lines(frame)
            )
            
            zone, walls, obstacles, corner_lines = await asyncio.gather(*futures)

            # Some check for end condition here

            if zone:
                if walls: # if some_math(walls) < some_constant:
                    state = "Follow wall"

                elif obstacles:
                    state = "Avoid obstacles"

                elif corner_lines:
                    state = "Turn"

                else:
                    state = "Follow wall"

            match state:
                case "Avoid obstacles":
                    # Create a series of commands to avoid obstacles.
                    pass
                
                case "Turn":
                    # Create a series of commands to turn to the next straight section.
                    pass

                case _, "Follow wall":
                    # Create a series of commands to follow the inside wall.
                    pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
        exitcode = 0
    except KeyboardInterrupt:
        logger.error("Process Interupted by User")
        exitcode = 0
    except Exception:
        logger.exception("A FATAL EXECPTION HAS OCCURED")
        exitcode = 1
    finally:
        logger.info(f"Cleaning up with exitcode {exitcode}...")
        logger.remove()
        sys.exit(exitcode)
