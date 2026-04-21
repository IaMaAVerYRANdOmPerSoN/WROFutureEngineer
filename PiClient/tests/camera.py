# Test passed.
import asyncio
import time
import numpy as np
import cv2
import multiprocessing as mp
from multiprocessing import shared_memory
from src.modules.asyncCamera import AsyncCamera
from src.modules.visionProcessing import AsyncMultiprocessingVisionProcessor
from src import logger
from src.modules.config import Config


async def test_single_frame():
    logger.info("Test 1: Single Frame Retrieval")
    async with AsyncCamera() as camera:
        await asyncio.sleep(2)
        frame = await camera.get_frame_async()
        assert isinstance(frame, np.ndarray), "Frame is not a numpy array"
        assert frame.shape == (Config.CameraConfig().OUTPUT_HEIGHT - Config.CameraConfig().INITIAL_ROI,
                               Config.CameraConfig().OUTPUT_WIDTH, Config.CameraConfig().OUTPUT_CHANNELS), f"Incorrect shape: {frame.shape}"
        logger.success("Single frame test passed!")
        bgr_frame = cv2.cvtColor(frame, cv2.COLOR_YUV2BGR)
        cv2.imwrite("Image.png", bgr_frame)


def stream_camera_in_subprocess(*args, **kwargs):
    async def run(*args, **kwargs):
        async with AsyncCamera() as camera:
            await camera.stream(*args, **kwargs)
    asyncio.run(run(*args, **kwargs))


async def test_streaming_pipe():
    logger.info("Test 2: Multiprocessing Pipe Stream")

    shm = shared_memory.SharedMemory(
        "frameBuffer",
        create=True,
        size=(
            Config.CameraConfig().OUTPUT_HEIGHT -
            Config.CameraConfig().INITIAL_ROI)
        * Config.CameraConfig().OUTPUT_WIDTH
        * Config.CameraConfig().OUTPUT_CHANNELS
        + 128
    )

    cam_receiver, cam_sender = mp.Pipe(duplex=False)
    camera_process = mp.Process(
        target=stream_camera_in_subprocess, args=(shm.name, cam_sender,))
    camera_process.start()
    await asyncio.sleep(2)  # Give the camera process time to initialize

    try:
        frame_counter = 0
        window_start = time.perf_counter()
        async for result in AsyncMultiprocessingVisionProcessor.async_pipe_reader(cam_receiver):
            if result == True:
                frame = shm.buf  # simulated computation
                frame_counter += 1
                if frame_counter % 30 == 0:
                    elapsed = (time.perf_counter() - window_start) * 1000
                    fps = 30 / (elapsed / 1000) if elapsed > 0 else float("inf")
                    logger.success(
                        f"Successfully fetched 30 frames: Average Framerate {fps:.2f} fps.")
                    return True
                
    finally:
        camera_process.terminate()
        camera_process.join()
        shm.close()
        shm.unlink()


async def run_tests():
    logger.info("Starting Camera Unittest...")
    await test_single_frame()
    await test_streaming_pipe()
