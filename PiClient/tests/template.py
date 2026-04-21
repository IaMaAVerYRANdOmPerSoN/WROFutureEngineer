import asyncio
import sys
from src import logger
from src.modules.commProtocol import Client
from src.modules.visionProcessing import AsyncMultiprocessingVisionProcessor
from src.modules.asyncCamera import AsyncCamera

async def run_tests():
    async with Client() as client, AsyncMultiprocessingVisionProcessor() as vision, AsyncCamera() as camera:
        pass
