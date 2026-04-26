import asyncio
import sys
from src import logger
from src.modules.comm_protocol import Client
from src.modules.vision_processing import AsyncMultiprocessingVisionProcessor
from src.modules.async_camera import AsyncCamera
from src.modules.subprocess_context_managers import camera_process_context_manager, vision_process_context_manager


async def run_tests():
    async with Client() as client:
        pass
