# Test passed.
import asyncio
import time
import numpy as np
import cv2
import multiprocessing as mp
from multiprocessing import shared_memory
from asyncCamera import AsyncCamera
from loguru import logger

def run_stream(shm_name, pipe_sender):
        async def _run():
            async with AsyncCamera() as cam:
                await cam.stream(shm_name, pipe_sender)
        asyncio.run(_run())

async def test_single_frame():
    logger.info("Test 1: Single Frame Retrieval")
    async with AsyncCamera() as camera:
        frame = await camera.get_frame_async()
        assert isinstance(frame, np.ndarray), "Frame is not a numpy array"
        assert frame.shape == (384, 512, 3), f"Incorrect shape: {frame.shape}"
        logger.success("Single frame test passed!")
        bgr_frame = cv2.cvtColor(frame, cv2.COLOR_YUV2BGR)
        cv2.imwrite("Image.png", bgr_frame)

async def test_streaming_pipe():
    logger.info("Test 2: Multiprocessing Pipe Stream")

    receiver, sender = mp.Pipe(duplex=False)
    shm = shared_memory.SharedMemory("frameBuffer", create=True, size=384*512*3 + 100)
    cam_process = mp.Process(None, run_stream, args=("frameBuffer", sender,))
    cam_process.start()

    try:
        frame_counter = 0
        start = time.time()
        async for result in AsyncCamera.frame_yeilder(receiver): # Now a classmethod!
            if result == True:
                frame = shm.buf # simulated computation
                frame_counter += 1
                if frame_counter % 30 == 0:
                    logger.success(f"Successfully fetched 30 frames: Average Framerate {1/(time.time()-start) * 30:.2f}.")
                    return True
                
    finally:
        cam_process.terminate()
        cam_process.join()
        shm.close()
        shm.unlink()

async def run_all_tests():
    try:
        await test_single_frame()
        await asyncio.sleep(0.5)
        await test_streaming_pipe()
        logger.success("ALL CAMERA TESTS PASSED")
    except Exception as e:
        logger.exception("Tests failed.")

if __name__ == "__main__":
    asyncio.run(run_all_tests())
# Test Passed.