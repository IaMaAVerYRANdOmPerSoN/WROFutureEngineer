import asyncio
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from loguru import logger
import picamera2
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
        self.executor = ThreadPoolExecutor(3) 
        
        try:
            self._cam = await asyncio.wait_for(
                self.loop.run_in_executor(self.executor, picamera2.Picamera2), 
                timeout=2.0
            )

            sensor_config = {
                "output_size": (640, 480),
                "bit_depth": 10
            }

            # 2. Define Controls to force speed
            controls_config = {
                # Lock frame rate to 60 FPS (min/max duration = 16.6ms)
                "FrameDurationLimits": (16666, 16666), 
                "AeEnable": True, 
            }
            config = self._cam.create_preview_configuration(main=self._config, sensor = sensor_config, controls=controls_config)

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
            await self.loop.run_in_executor(self.executor, self._cam.close)
            self._cam = None
        
        if hasattr(self, "executor") and self.executor:
            self.executor.shutdown(wait=False)
        
    async def get_frame_async(self, timeout = 1):
        """
        Fetch a frame asyncronously from `self._cam`
        
        :param self: The instance of `AsyncCamera`
        :param timeout: The maximum roundtrip time, in seconds, before raising asyncio.TimeoutError
        :returns: frame: a 3D array of shape `Vres * Hres * 3` Where each pixel is represented in YUV color space.
        """
        while self.failures <= 10:
            try:
                frame = await asyncio.wait_for(self.loop.run_in_executor(self.executor, self._cam.capture_array), timeout)
                frame = frame.flatten()
                y_end = 512*384
                u_end = y_end + (256*192)

                y_plane = frame[:y_end].reshape((384, 512))
                u_plane_raw = frame[y_end:u_end].reshape((192, 256))
                v_plane_raw = frame[u_end:].reshape((192, 256))

                u_plane = np.broadcast_to(u_plane_raw[:, None, :, None], (192, 2, 256, 2)).reshape((384, 512))
                v_plane = np.broadcast_to(v_plane_raw[:, None, :, None], (192, 2, 256, 2)).reshape((384, 512))

                full_yuv = np.dstack((y_plane, u_plane, v_plane))
                self.failures = 0
                logger.info(f"Fetched new frame from PiCamera sucessfully")
                return np.ascontiguousarray(full_yuv)
            
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
            
            return None

    async def buffer_frames_async(self, num_frames = 5, timeout = 1.0):
            """
            Buffers `num_frames` frames asynchronously.
            
            :param self: The instance of `AysncCamera`.
            :param num_frames: The number of frames to buffer.
            :param timeout: Global timeout for buffering frames.
            :returns: `list[tuple[tuple[tuple[float, float, float]]]]`, where each element in the list represents a frame in YUV colorspace.
            """
            return [await asyncio.wait_for(self.get_frame_async(), timeout) for _ in range(num_frames)]
        
    async def stream(self, shm, sender: "mp.connections.Connection"):
        """
        asynchronous indefinite yield camera IOstream.
        
        :param self: The instance of AsyncCamera.
        :yields: `tuple[tuple[tuple[float, float, float]]]`, an `vres * hres * 3` array representing the image in YUV colorspace.
        :returns: `None`
        """
        shm = shared_memory.SharedMemory(name=shm)
        array = np.ndarray((384, 512, 3), dtype=np.uint8, buffer=shm.buf)

        while True:
            frame = await self.get_frame_async()
            if frame is not None:
                array[:] = frame[:]
                sender.send(True)
                
    @classmethod
    async def frame_yeilder(self, receiver):
        while True:
            if receiver.poll():
                yield receiver.recv()
            else:
                await asyncio.sleep(0)