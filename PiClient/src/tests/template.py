import asyncio
import sys
from src import logger
from src.modules.comm_protocol import Client
from src.modules.vision_processing import AsyncMultiprocessingVisionProcessor
from src.modules.async_camera import AsyncCamera


async def run_tests():
    async with Client() as client:
        pass
