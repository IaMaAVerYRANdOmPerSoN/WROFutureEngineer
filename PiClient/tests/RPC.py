# Test Passed.
import asyncio
import sys
from loguru import logger
from src.commProtocol import Client

# The "Drive in a straight line while blinking the LED test."
async def drive_and_blink_test(client):
    for i in range(5):
            drive_task = asyncio.create_task(client.drive_motors(i * 0.05, 0, 5)) # Drive forward at 10% speed, straight for 5 seconds

            for _ in range(100):
                await client.set_led_state(1.0)
                await client.set_led_state(0.0)
                await asyncio.sleep(0.1)

            await asyncio.wait_for(drive_task, timeout=30.0) # Will update this dynamically later
            await asyncio.sleep(0.3)

# Drive in an S-Shape test
async def drive_s_shape_test(client):
    for i in range(3):
        await client.drive_motors(i*0.1, 45, 2) # Drive 10% speed @ 45 degrees for 2 seconds
        await asyncio.sleep(0.5)
        await client.drive_motors(i*0.1, -45, 2)
        await asyncio.sleep(0.5)

# Drive in a circle test, testing the turn radius and the differential
async def drive_circle_test(client):
    for i in range(3):
        await client.drive_motors(i*0.1, 90, 4) # Maximum turn for 4 seconds
        await asyncio.sleep(0.5)

# Drive back-and-forth test, testing precision and response time (should end up at the starting point)
async def drive_back_and_forth_test(client):
    for i in range(10):
        await client.drive_motors(i*0.02, 0, 0.3)
        # Hopefully this sudden change doesn't explode the bldc, but I mean that's what the test is for right?
        await client.drive_motors(i*0.02, 180, 0.3)
        await asyncio.sleep(0.5)

async def run_tests():
    logger.info("Starting RPC Unittest...")
    async with Client() as client:
        await asyncio.sleep(2)
        if not await client.verify_connection():
            return
        
        await drive_and_blink_test(client)
        await drive_s_shape_test(client)
        await drive_circle_test(client)
        await drive_back_and_forth_test(client)