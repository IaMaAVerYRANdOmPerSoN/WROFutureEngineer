# Test Passed.
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
    async with Client() as client:
        await asyncio.sleep(2)
        if not await client.verify_connection():
            return
        
        await asyncio.sleep(0.5)

        while True:  
            drive_task = asyncio.create_task(client.arc_spline(7, [[1, 4], [3, 18], [6, 14], [7, 11], [7, 13], [7, 18], [8, 10], [10, 19], [11, 12], [13, 16]]))
            await asyncio.sleep(0) # let the task run

            for _ in range(100):
                await client.set_led_state(1.0)
                await client.get_servo_angle()
                await client.get_encoder_value()
                await client.set_led_state(0.0)
                await asyncio.sleep(0.1)

            await asyncio.wait_for(drive_task, timeout=30.0) # Will update this dynamically later
            await asyncio.sleep(0.15)

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
# Test Passed.