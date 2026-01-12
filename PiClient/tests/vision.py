import asyncio
from asyncCamera import AsyncCamera
from visionProcessing import AsyncVisionProcessor
import numpy as np
from loguru import logger
import multiprocessing as mp
from multiprocessing import shared_memory
import sys

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
    shm = shared_memory.SharedMemory(name="frameBuffer", create=True, size=384*512*3 + 128) # Frame + 128 bytes margin
    frameReceiver, frameSender = mp.Pipe(duplex=False)
    dataReceiver, dataSender = mp.Pipe(duplex=False)

    camera_stream = mp.Process(group=None, target=camera, args=("frameBuffer", frameSender,), daemon=False)
    camera_stream.start()

    data_stream = mp.Process(group=None, target=vision, args=("frameBuffer", dataSender, frameReceiver,), daemon=False)
    data_stream.start()
        
    try:
        logger.info("Starting Vision Unittest...")
        async for zone, walls, obstacles, corner_lines, wall_dists, obstacle_dists in AsyncVisionProcessor.data_yielder(dataReceiver):
                logger.error( # Error so I don't have to open a verbose log file to find stuff
                    f"Zone {zone}\n" \
                    f"Walls: {walls} \n" \
                    f"Obstacles: {obstacles} \n" \
                    f"Corner Lines: {corner_lines} \n" \
                    f"Wall distances {wall_dists} \n" \
                    f"Obstacle Distances {obstacle_dists} \n")
    except KeyboardInterrupt:
        logger.error("Test terminated by user")
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
    