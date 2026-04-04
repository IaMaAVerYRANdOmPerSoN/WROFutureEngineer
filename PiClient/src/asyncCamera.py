import asyncio
from multiprocessing.connection import Connection
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from loguru import logger
import picamera2 # type: ignore TODO: Get the .pyi file from the picamera2 repo and add it to the project so my stuff gets linted.
import multiprocessing as mp
from multiprocessing import shared_memory

class AsyncCamera():
    def __init__(self, config = {"format": "YUV420", "size": (512, 384)}):
        """
        The constructor for the AsyncCamera class.
        
        :param self: The instance of `AsyncCamera`.
        :param config: A PiCamera2 configuration dictionary passed to `picamera2.Picamera2.create_preview_configuration()`.
        """
        self._config = config
        self._cam = None

        self.loop = asyncio.get_event_loop()
        self.executor = None
        self.INITIAL_ROI = 100 # Let's say drop top 100 pixels, will add dynamic runtime tunning hopefully
        

    async def __aenter__(self):
        """
        Initializes hardware resources defined in __init__ asynchronously.

        :param self: The instance of `AsyncCamera`.
        :raises: `ConnectionError` if an exception occurs or the camera times out.

        :returns: `self`: the instance of `AsyncCamera`
        """
        self.executor = ThreadPoolExecutor(3) 
        self._capture_semaphore = asyncio.Semaphore(2) # Limit the number of concurrent captures to prevent overwhelming the camera hardware (and the event loop)
        
        try:
            self._cam = await asyncio.wait_for(
                self.loop.run_in_executor(self.executor, picamera2.Picamera2), 
                timeout=2.0
            )

            sensor_config = {
                "output_size": (640, 480),
                "bit_depth": 10
            }

            controls_config = {
                "FrameDurationLimits": (33333, 33333), 
                "AeEnable": True, 
            }
            config = self._cam.create_preview_configuration(
                main=self._config,
                sensor=sensor_config,
                raw=None,
                controls=controls_config,
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
                y_end = 512*384
                u_end = y_end + (256*192)

                y_plane = frame[:y_end].reshape((384, 512))
                u_plane_raw = frame[y_end:u_end].reshape((192, 256))
                v_plane_raw = frame[u_end:].reshape((192, 256))

                y_plane = y_plane[self.INITIAL_ROI:, :]
                u_plane_raw = u_plane_raw[self.INITIAL_ROI//2:, :]
                v_plane_raw = v_plane_raw[self.INITIAL_ROI//2:, :]

                u_plane = u_plane_raw.repeat(2, axis=0).repeat(2, axis=1)
                v_plane = v_plane_raw.repeat(2, axis=0).repeat(2, axis=1)

                full_yuv = np.dstack((y_plane, u_plane, v_plane))

                shm = shared_memory.SharedMemory(name=shm_name)
                buffer = np.ndarray((384, 512, 3), dtype=np.uint8, buffer=shm.buf)
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