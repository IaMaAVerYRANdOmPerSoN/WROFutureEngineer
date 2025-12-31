# Test Passed.
import asyncio
import sys
from loguru import logger
from commProtocol import Client

logger.remove()
fmt = (
    "<blue>[{time:HH:mm:ss:SSS}]</blue> │ "
    "<cyan>{line:03}: {function: <18}</cyan> │ "
    "<level>{level: <8}</level> │ "
    "<level>{message}</level>")
logger.add(sys.stderr, level="INFO", format=fmt)
logger.add("log.txt", level="WARNING", enqueue=True, rotation="5 MB", retention="10 days", format=fmt)
logger.add("verbose.txt", level="DEBUG", enqueue=True, rotation="1 MB", retention="3 days", format=fmt, backtrace=True, diagnose=True)

async def main():
    async with Client() as client:
        await asyncio.sleep(2)
        if not await client.verify_connection():
            return
        
        await asyncio.sleep(0.5)

        while True:  
            drive_task = asyncio.create_task(client.drive_motors(100, 12))
            await asyncio.sleep(0) # let the task run
            await client.set_servo_angle(180)
            await client.set_servo_angle(0)
            await client.set_servo_angle(180)
            await client.set_servo_angle(0)
            await asyncio.sleep(0.5)

            for _ in range(100):
                await client.set_led_state(1.0)
                await client.set_led_state(0.0)
                await asyncio.sleep(0.1)

            await asyncio.wait_for(drive_task, timeout=30.0) # Will update this dynamically later
            await asyncio.sleep(0.3)

if __name__ == "__main__":
    try:
        asyncio.run(main())
        exitcode = 0
    except KeyboardInterrupt:
        logger.error("Process Interrupted by User")
        exitcode = 0
    except Exception:
        logger.exception("A FATAL EXCEPTION HAS OCCURRED")
        exitcode = 1
    finally:
        logger.info(f"Cleaning up with exitcode {exitcode}...")
        logger.remove()
        sys.exit(exitcode)
# Test Passed.