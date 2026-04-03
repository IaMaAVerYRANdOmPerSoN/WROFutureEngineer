# Test Passed.
import asyncio
import sys
from loguru import logger
from src.commProtocol import Client

async def run_tests():
    logger.info("Starting RPC Unittest...")
    async with Client() as client:
        await asyncio.sleep(2)
        if not await client.verify_connection():
            return
        
        await asyncio.sleep(0.5)

        while True:  
            drive_task = asyncio.create_task(client.drive_motors(0.1, 0, 12)) # Drive forward at 10% speed, straight for 12 seconds
            await asyncio.sleep(0) # let the task run
            await client.set_servo_angle(90)
            await asyncio.sleep(0.5)
            await client.set_servo_angle(180)
            await asyncio.sleep(0.5)
            await client.set_servo_angle(0)
            await asyncio.sleep(0.5)
            await client.set_servo_angle(180)
            await asyncio.sleep(0.5)
            await client.set_servo_angle(0)
            await asyncio.sleep(0.5)

            for _ in range(100):
                await client.set_led_state(1.0)
                await client.set_led_state(0.0)
                await asyncio.sleep(0.1)

            await asyncio.wait_for(drive_task, timeout=30.0) # Will update this dynamically later
            await asyncio.sleep(0.3)