import asyncio
from multiprocessing.connection import Connection
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from loguru import logger
import picamera2 # type: ignore TODO: Get the .pyi file from the picamera2 repo and add it to the project so my stuff gets linted.
from multiprocessing import shared_memory
from config import Config
from typing import Dict

class AsyncCamera():
    def __init__(self, config = Config.CameraConfig().FORMAT, sensor_config = Config.CameraConfig().SENSOR_CONFIG, controls_config = Config.CameraConfig().CONTROLS_CONFIG,):
        """
        The constructor for the AsyncCamera class.
        
        :param self: The instance of `AsyncCamera`.
        :param config: A PiCamera2 configuration dictionary passed to `picamera2.Picamera2.create_preview_configuration()`.
        """
        self._CONFIG: Dict = config
        self._SENSOR_CONFIG: Dict = sensor_config
        self._CONTROLS_CONFIG: Dict = controls_config
        self._cam = None

        self.FRAME_SIZE = self._CONFIG["size"]

        self.loop = asyncio.get_event_loop()
        self.executor = None
        self.INITIAL_ROI = Config.CameraConfig().INITIAL_ROI
        

    async def __aenter__(self):
        """
        Initializes hardware resources defined in __init__ asynchronously.

        :param self: The instance of `AsyncCamera`.
        :raises: `ConnectionError` if an exception occurs or the camera times out.

        :returns: `self`: the instance of `AsyncCamera`
        """
        self.executor = ThreadPoolExecutor(Config.CameraConfig.EXECUTOR_THREADS) 
        self._capture_semaphore = asyncio.Semaphore(Config.CameraConfig.MAX_CONCURRENT_CAPTURES)
        
        try:
            self._cam = await asyncio.wait_for(
                self.loop.run_in_executor(self.executor, picamera2.Picamera2), 
                timeout=2.0
            )

            config = self._cam.create_preview_configuration(
                main=self._CONFIG,
                sensor=self._SENSOR_CONFIG,
                raw=None,
                controls=self._CONTROLS_CONFIG,
                buffer_count=2,
            )

            await asyncio.wait_for(
                self.loop.run_in_executor(self.executor, self._cam.configure, config),
                timeout=1.0
            )
            await asyncio.wait_for(
                self.loop.run_in_executor(self.executor, self._cam.start),
                timeout=1.0
            )

            logger.info(f"Camera configuration applied: {self._cam.camera_configuration()}")

            return self
    
        except (asyncio.TimeoutError, Exception) as e:
            logger.critical(f"Camera Hardware Initialization Failed: {e}")
            raise ConnectionError("Camera not responding during power-up.") from e

    async def __aexit__(self, *args): # Let the main loop handle the logging and execeptions
        if hasattr(self, "_cam") and self._cam:
            await self.loop.run_in_executor(self.executor, self._cam.stop)
            await self.loop.run_in_executor(self.executor, self._cam.close)
            self._cam = None
        
        if hasattr(self, "executor") and self.executor:
            self.executor.shutdown(wait=False)
        
    async def get_frame_async(self, timeout = 0.1, shm_name = None):
        """
        Fetch a frame asynchronously from `self._cam`
        
        :param self: The instance of `AsyncCamera`
        :param timeout: The maximum roundtrip time, in seconds, before raising asyncio.TimeoutError
        :returns: frame: a 3D array of shape `Vres * Hres * 3` Where each pixel is represented in YUV color space.
        """
        
        while True:
            try:
                async with self._capture_semaphore:
                    frame: np.ndarray = await asyncio.wait_for(self.loop.run_in_executor(self.executor, self._cam.capture_array), timeout=timeout)
                
                frame = frame.flatten()
                y_end = self.FRAME_SIZE[0]*self.FRAME_SIZE[1]
                u_end = y_end + (self.FRAME_SIZE[0]//2 * self.FRAME_SIZE[1]//2)

                y_plane = frame[:y_end].reshape(self.FRAME_SIZE)
                u_plane_raw = frame[y_end:u_end].reshape((self.FRAME_SIZE[0]//2, self.FRAME_SIZE[1]//2))
                v_plane_raw = frame[u_end:].reshape((self.FRAME_SIZE[0]//2, self.FRAME_SIZE[1]//2))

                y_plane = y_plane[self.INITIAL_ROI:, :]
                u_plane_raw = u_plane_raw[self.INITIAL_ROI//2:, :]
                v_plane_raw = v_plane_raw[self.INITIAL_ROI//2:, :]

                u_plane = u_plane_raw.repeat(2, axis=0).repeat(2, axis=1)
                v_plane = v_plane_raw.repeat(2, axis=0).repeat(2, axis=1)

                full_yuv = np.dstack((y_plane, u_plane, v_plane))

                shm = shared_memory.SharedMemory(name=shm_name)
                buffer = np.ndarray((self.FRAME_SIZE[0], self.FRAME_SIZE[1], 3), dtype=np.uint8, buffer=shm.buf)
                np.copyto(buffer, full_yuv)

                logger.info(f"Fetched new frame from PiCamera successfully")
            
            except asyncio.TimeoutError:
                logger.warning("Camera frame capture timed out, retrying...")
                await asyncio.sleep(0.03) # Give some grace

            except Exception as e:
                logger.warning(f"Unexpected error during frame capture: {e}, continuing...")
                await asyncio.sleep(0.01)

    async def buffer_frames_async(self, num_frames = 5, timeout = 1.0):
            """
            Buffers `num_frames` frames asynchronously.
            
            :param self: The instance of `AysncCamera`.
            :param num_frames: The number of frames to buffer.
            :param timeout: Global timeout for buffering frames.
            :returns: `list[tuple[tuple[tuple[float, float, float]]]]`, where each element in the list represents a frame in YUV colorspace.
            """
            return [await asyncio.wait_for(self.get_frame_async(), timeout) for _ in range(num_frames)]
        
    async def stream(self, shm, sender: Connection):
        """
        asynchronous indefinite yield camera IOstream.
        
        :param self: The instance of AsyncCamera.
        :yields: `tuple[tuple[tuple[float, float, float]]]`, an `vres * hres * 3` array representing the image in YUV colorspace.
        :returns: `None`
        """

        while True:
            await self.get_frame_async(shm_name=shm)
            sender.send(True) # Signal that a new frame is ready, the frame itself is in shared memory so we dont have to send it through the pipe.
                
    @staticmethod
    async def frame_yielder(receiver: Connection):
        while True:
            if receiver.poll():
                yield receiver.recv()
            else:
                await asyncio.sleep(0)