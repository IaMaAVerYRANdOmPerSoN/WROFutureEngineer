import asyncio
from multiprocessing.connection import Connection
import multiprocessing as mp
from multiprocessing import shared_memory
import cv2
from tests.vision import _draw_detections
from utils import logger
from src.visionProcessing import VisionObject, AsyncMultiprocessingVisionProcessor, OpenChallengeAsyncMultiprocessingVisionProcessor
from src.asyncCamera import AsyncCamera
from src.config import Config
import numpy as np


class BaseTool:
    def __init__(self, name, description):
        self.name = name
        self.description = description
        self.frame = np.zeros((Config.CameraConfig.OUTPUT_HEIGHT - Config.CameraConfig.INITIAL_ROI, Config.CameraConfig.OUTPUT_WIDTH, Config.CameraConfig.OUTPUT_CHANNELS), dtype=np.uint8)

    def _draw_vision_object(self, object: VisionObject, color: tuple, frame):
        assert isinstance(frame, np.ndarray), logger.error("Frame cannot be None")
        contour = object.contour
        if contour is not None:
            cv2.drawContours(frame, [contour], -1, color, 2)
            x, y, w, h = object.bbox
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            cv2.circle(frame, (int(object.x_centroid), int(object.y_centroid)), 3, color, -1)

    def _vision_process_manager(self, shm_name: str, receiver: Connection, sender: Connection, **kwargs):
        async def _run(*args, **kwargs):
            async with AsyncMultiprocessingVisionProcessor() as processor:
                await processor.comprehensive_analysis(shm_name, receiver, sender, *args, **kwargs)
        
        asyncio.run(_run())

    def _no_perspective_vision_process_manager(self, shm_name: str, receiver: Connection, sender: Connection, **kwargs):
        async def _run(*args, **kwargs):
            async with OpenChallengeAsyncMultiprocessingVisionProcessor() as processor:
                await processor.comprehensive_analysis(shm_name, receiver, sender, *args, **kwargs)
        
        asyncio.run(_run())

    def _camera_process_manager(self, shm_name: str, sender: Connection):
        async def _run(*args, **kwargs):
            async with AsyncCamera() as camera:
                await camera.stream(shm_name, sender, *args, **kwargs)
        
        asyncio.run(_run())

    def _draw(self, *args, **kwargs):
        raise NotImplementedError("Subclasses must implement the _draw method")
    
    def _draw_no_perspective(self, *args, **kwargs):
        raise NotImplementedError("Subclasses must implement the _draw_no_perspective method")

    async def run(self, *args, **kwargs):
        try:
            logger.info(f"Running {self.name} tool...")
            shm = shared_memory.SharedMemory(name=f"{self.name}_shm")
            camera_sender, camera_receiver = mp.Pipe()
            vision_sender, vision_receiver = mp.Pipe()
            no_perspective_camera_sender, no_perspective_camera_receiver = mp.Pipe()
            no_perspective_vision_sender, no_perspective_vision_receiver = mp.Pipe()

            camera_process = mp.Process(target=self._camera_process_manager, args=(shm.name, camera_sender, no_perspective_camera_sender))
            vision_process = mp.Process(target=self._vision_process_manager, args=(shm.name, camera_receiver, vision_sender))
            no_perspective_vision_process = mp.Process(target=self._no_perspective_vision_process_manager, args=(shm.name, no_perspective_camera_receiver, no_perspective_vision_sender))

            camera_process.start()
            vision_process.start()
            no_perspective_vision_process.start()

            vision_reader = AsyncMultiprocessingVisionProcessor.async_pipe_reader(vision_receiver)
            no_perspective_reader = AsyncMultiprocessingVisionProcessor.async_pipe_reader(no_perspective_vision_receiver)
            vision_iter = vision_reader.__aiter__()
            no_perspective_iter = no_perspective_reader.__aiter__()

            while True:
                try:
                    data, perspectivless_data = await asyncio.gather(
                        anext(vision_iter),
                        anext(no_perspective_iter),
                    )
                except StopAsyncIteration:
                    break
                self.frame = cv2.cvtColor(np.frombuffer(shm.buf, dtype=np.uint8) \
                    .reshape((
                        Config.CameraConfig.OUTPUT_HEIGHT
                        - Config.CameraConfig.INITIAL_ROI,
                        Config.CameraConfig.OUTPUT_WIDTH,
                vision_process.terminate() if vision_process.is_alive() else None
                no_perspective_vision_process.terminate() if no_perspective_vision_process.is_alive() else None
                camera_process.join(
                    timeout=1) if camera_process.is_alive() else None
                vision_process.join(
                    timeout=1) if vision_process.is_alive() else None
                no_perspective_vision_process.join(
                    timeout=1) if no_perspective_vision_process.is_alive() else None
        finally:
            logger.info(
                "Terminating processes and destroying shared memory... ")
            try:
                camera_process.terminate() if camera_process.is_alive() else None
                vision_process.terminate() if vision_process.is_alive() else None
                camera_process.join(
                    timeout=1) if camera_process.is_alive() else None
                vision_process.join(
                    timeout=1) if vision_process.is_alive() else None
                shm.close()
                shm.unlink()
                logger.info("Done")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
                logger.warning(
                    f"Leaked memory segments and processes may need to be cleaned up manually. Good luck finding them michael -_-")
