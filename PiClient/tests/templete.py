import asyncio
import sys
from loguru import logger
from src.commProtocol import Client
from src.visionProcessing import AsyncMultiprocessingVisionProcessor
from src.asyncCamera import AsyncCamera

logger.remove()
fmt = (
    "<blue>[{time:HH:mm:ss:SSS}]</blue> │ "
    "<cyan>{line:03}: {function: <18}</cyan> │ "
    "<level>{level: <8}</level> │ "
    "<level>{message}</level>")
logger.add(sys.stderr, level="WARNING", format=fmt)
logger.add("log.txt", level="WARNING", enqueue=True, rotation="5 MB", retention="10 days", format=fmt)
logger.add("verbose.txt", level="DEBUG", enqueue=True, rotation="1 MB", retention="3 days", format=fmt, backtrace=True, diagnose=True)

async def run_tests():
    async with Client() as client, AsyncMultiprocessingVisionProcessor() as vision, AsyncCamera() as camera:
        pass