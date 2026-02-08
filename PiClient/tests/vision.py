import asyncio
from asyncCamera import AsyncCamera
from visionProcessing import AsyncVisionProcessor
import numpy as np
from loguru import logger
import multiprocessing as mp
from multiprocessing import shared_memory
import sys

logger.remove()
logger.add("vision.log", rotation="1 MB", retention="10 days", level="INFO")
logger.add(sys.stdout, level="INFO", filter=lambda record: record["level"].no < logger.level("ERROR").no)
logger.add(sys.stderr, level="ERROR")

def camera(shm, sender):
    async def _run():
        async with AsyncCamera() as camera:
            await camera.stream(shm, sender)

    asyncio.run(_run())

def vision(shm, sender, receiver):
    async def _run():
        async with AsyncVisionProcessor() as vision:
            await vision.comprehensive_analysis(shm, sender, receiver)
    
    asyncio.run(_run())

async def main():
    shm_name = "frameBuffer"
    shm_size = 384*512*3 + 128  # Frame + 128 bytes margin

    try:
        shm = shared_memory.SharedMemory(name=shm_name, create=True, size=shm_size)
    except FileExistsError:
        # Clean up any stale shared memory segment from a previous run and retry
        try:
            existing_shm = shared_memory.SharedMemory(name=shm_name, create=False)
            existing_shm.close()
            existing_shm.unlink()
        except FileNotFoundError:
            # The shared memory segment disappeared between create and cleanup attempts
            pass
        shm = shared_memory.SharedMemory(name=shm_name, create=True, size=shm_size)

    frameReceiver, frameSender = mp.Pipe(duplex=False)
    dataReceiver, dataSender = mp.Pipe(duplex=False)

    camera_stream = mp.Process(group=None, target=camera, args=(shm_name, frameSender,), daemon=False)
    camera_stream.start()

    data_stream = mp.Process(group=None, target=vision, args=(shm_name, dataSender, frameReceiver,), daemon=False)
    frameReceiver, frameSender = mp.Pipe(duplex=False)
    dataReceiver, dataSender = mp.Pipe(duplex=False)

    camera_stream = mp.Process(group=None, target=camera, args=("frameBuffer", frameSender,), daemon=False)
    camera_stream.start()

    data_stream = mp.Process(group=None, target=vision, args=("frameBuffer", dataSender, frameReceiver,), daemon=False)
    data_stream.start()
        
    try:
        logger.info("Starting Vision Unittest...")
        async for zone, walls, obstacles, corner_lines, wall_dists, obstacle_dists in AsyncVisionProcessor.data_yielder(dataReceiver):
                logger.info(
                    f"Zone {zone}\n" \
                    f"Walls: {walls} \n" \
                    f"Obstacles: {obstacles} \n" \
                    f"Corner Lines: {corner_lines} \n" \
                    f"Wall distances {wall_dists} \n" \
                    f"Obstacle Distances {obstacle_dists} \n")
    except KeyboardInterrupt:
        logger.info("Test terminated by user")
    except Exception:
        logger.critical("A FATAL EXCEPTION HAS OCCURRED")
        logger.exception("Traceback:")
    finally:
        logger.info("Cleaning up child processing and leaked memory items...")
        camera_stream.terminate()
        data_stream.terminate()
        shm.close()
        shm.unlink()
        logger.info("Exiting...")
        sys.exit()

if __name__ == "__main__":
    asyncio.run(main())
    