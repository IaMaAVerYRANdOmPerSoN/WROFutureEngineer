import asyncio
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from loguru import logger
import picamera2

class AsyncCamera():
    def __init__(self, config = {"format": "YUV444", "size": (160, 120)}):
        """
        The constructor for the AsyncCamera class.
        
        :param self: The instance of `AsyncCamera`.
        :param config: A PiCamera2 configuration dictionary passed to `picamera2.Picamera2.create_preview_configuration()`.
        """
        self._config = config
        self._cam = None
        self.FRAMERATE = 30

        self.failures = 0
        self.loop = asyncio.get_event_loop()
        self.executor = None
        

    async def __aenter__(self):
        """
        Initializes hardware resources defined in __init__ asyncrounously.

        :param self: The instance of `AsyncCamera`.
        :raises: `ConnectionError` if an execption occurs or the camera times out.

        :returns: `self`: the instance of `AsyncCamera`
        """
        self.executor = ThreadPoolExecutor(8) 
        
        try:
            self._cam = await asyncio.wait_for(
                self.loop.run_in_executor(self.executor, picamera2.Picamera2), 
                timeout=2.0
            )

            config = self._cam.create_preview_configuration(main=self._config)

            await asyncio.wait_for(
                self.loop.run_in_executor(self.executor, self._cam.configure, config),
                timeout=1.0
            )
            await asyncio.wait_for(
                self.loop.run_in_executor(self.executor, self._cam.start),
                timeout=1.0
            )

            return self
    
        except (asyncio.TimeoutError, Exception) as e:
            logger.critical(f"Camera Hardware Initialization Failed: {e}")
            raise ConnectionError("Camera not responding during power-up.") from e

    async def __aexit__(self, *args): # Let the main loop handle the logging and execeptions
        if hasattr(self, "_cam") and self._cam:
            await self.loop.run_in_executor(self.executor, self._cam.stop)
        
        if hasattr(self, "executor") and self.executor:
            self.executor.shutdown(wait=False)
        
    async def get_frame_async(self, timeout = 0.2):
        """
        Fetch a frame asyncronously from `self._cam`
        
        :param self: The instance of `AsyncCamera`
        :param timeout: The maximum roundtrip time, in seconds, before raising asyncio.TimeoutError
        :returns: frame: a 3D array of shape `Vres * Hres * 3` Where each pixel is represented in YUV color space.
        """
        while self.failures <= 10:
            try:
                frame = await asyncio.wait_for(self.loop.run_in_executor(self.executor, self._cam.capture_array), timeout)
                self.failures = 0
                logger.info(f"Fetched new frame from PiCamera sucessfully")
                return np.ascontiguousarray(frame)
            
            except asyncio.TimeoutError:
                self.failures += 1
                if self.failures >= 10: 
                    raise MemoryError("Garbage threads have bulit up beyond safe threshold.") from asyncio.TimeoutError
                logger.error(f"Timed out awaiting video stream")

            except Exception as e:
                self.failures += 1
                if self.failures >= 10: 
                    raise IOError("Unacceptable buildup of IOerrors, last error: '{e}'")
                logger.error(f"Caught video stream exception: '{e}'")
            
            return "IO_ERR"

    async def buffer_frames_async(self, num_frames = 5, timeout = 1.0):
            """
            Buffers `num_frames` frames asynchronously.
            
            :param self: The instance of `AysncCamera`.
            :param num_frames: The number of frames to buffer.
            :param timeout: Global timeout for buffering frames.
            :returns: `list[tuple[tuple[tuple[float, float, float]]]]`, where each element in the list represents a frame in YUV colorspace.
            """
            return [await asyncio.wait_for(self.get_frame_async(), timeout) for _ in range(num_frames)]
        
    async def stream(self):
        """
        asynchronous indefinite yield camera IOstream.
        
        :param self: The instance of AsyncCamera.
        :yields: `tuple[tuple[tuple[float, float, float]]]`, an `vres * hres * 3` array representing the image in YUV colorspace.
        :returns: `None`
        """
        while True:
            frame = await self.get_frame_async()
            if frame is not None:
                yield frame

            await asyncio.sleep(1/self.FRAMERATE - 0.05)