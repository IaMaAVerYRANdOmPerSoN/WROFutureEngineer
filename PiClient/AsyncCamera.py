import asyncio
import cv2
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from loguru import logger
import picamera2

class Camera():
    def __init__(self, config = {"format": "YUV420", "size": (160, 120)}):
        self._config = config
        self._cam = None
        self.framerate = 30

        self.failiures = 0
        self.loop = asyncio.get_event_loop()
        self.executor = None
        

    async def __aenter__(self):
        self.executor = ThreadPoolExecutor(10) 
        
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

    async def __aexit__(self, *args): # Let the main loop handle the logging
        if hasattr(self, "_cam") and self._cam:
            await self.loop.run_in_executor(self.executor, self._cam.stop)
        
        if hasattr(self, "executor") and self.executor:
            self.executor.shutdown(wait=False)
        
    async def get_frame_async(self, timeout = 0.2):
        while self.failiures <= 10:
            try:
                frame = await asyncio.wait_for(self.loop.run_in_executor(self.executor, self._cam.capture_array()), timeout)
                self.failiures = 0
                logger.info(f"Fetched new frame from PiCamera sucessfully")
                return frame
            
            except asyncio.TimeoutError:
                self.failiures += 1
                if self.failiures >= 10: 
                    raise MemoryError("Garbage threads have bulit up beyond safe threshold.") from asyncio.TimeoutError
                logger.error(f"Timed out awaiting video stream")

            except Exception as e:
                self.failiures += 1
                if self.failiures >= 10: 
                    raise IOError("Unacceptable buildup of IOerrors, last error: '{e}'")
                logger.error(f"Caught video stream exception: '{e}'")
            
            finally:
                return "IO_ERR"

    async def buffer_frames_async(self, num_frames = 5, timeout = 1.0):
            return [await asyncio.wait_for(self.get_frame_async(), timeout) for _ in range(num_frames)]
        
    async def stream(self):
        while True:
            frame = await self.get_frame_async()
            if frame is not None:
                yield frame

            await asyncio.sleep(0.033) 