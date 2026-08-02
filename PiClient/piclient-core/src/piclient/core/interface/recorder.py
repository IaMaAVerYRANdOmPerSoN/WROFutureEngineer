"""
Provides class`Recorder`, which writes recorded test data from shm to disk.
"""

from typing import Self, NoReturn
from types import TracebackType

import asyncio
import time
import multiprocessing.shared_memory as shm
from os import makedirs
from multiprocessing.connection import Connection as PipeConnection

import cv2
import numpy as np
from loguru import logger

from ..lib import GLOBAL_CONFIG, export
from ..utils import async_pipe_reader as utils_async_pipe_reader, async_pipe_reader_fifo as utils_async_pipe_reader_fifo

@export
class Recorder:
    """A class for recording video data."""

    _DEFAULT_RESOLUTION: tuple[int, int, int] = GLOBAL_CONFIG().CameraConfig.OUTPUT_SHAPE
    _DEFAULT_FPS: float = GLOBAL_CONFIG().CameraConfig.FPS
    async_pipe_reader = staticmethod(utils_async_pipe_reader)
    async_pipe_reader_fifo = staticmethod(utils_async_pipe_reader_fifo)

    def __init__(self, writer: cv2.VideoWriter=cv2.VideoWriter(), resolution: tuple[int, int] | None=None, fps: float | None = None) -> None:
        self.resolution = (
            resolution 
            if resolution is not None 
            else self._DEFAULT_RESOLUTION
        )
        self.fps = (
            fps 
            if fps is not None 
            else self._DEFAULT_FPS
        )

        self.timestamp = 0
        self.writer = writer
        self.fourcc = self.writer.fourcc("H", "2", "6", "4")

    def _write(self, frame: np.ndarray) -> None:
        """Write a frame to the video file.

        :param frame: The frame to write.
        """
        if self.writer.isOpened():
            self.writer.write(frame)
        else:
            raise RuntimeError("VideoWriter is not opened. use the context manager first.")

    def __enter__(self) -> Self:
        """Enter the context manager.

        :return: The Recorder instance.
        """
        makedirs("WRO_recordings", exist_ok=True)
        self.timestamp = time.time()
        self.writer.open(
            f"WRO_recordings/recording_{int(self.timestamp)}.avi",
            self.fourcc,
            self.fps,
            self.resolution[:2]
        )
        return self

    def __exit__(self, exc_type: type[BaseException], exc_value: BaseException, traceback: TracebackType) -> None:
        """Exit the context manager and release the video writer."""
        self.writer.release()
        
    async def record(self, shm_name: str, receiver: PipeConnection) -> NoReturn: # pyright: ignore[reportReturnType]
        """record frames from shared memory and write them to the video file.

        :param shm_name: The name of the shared memory segment.
        :param receiver: The pipe connection to read from.
        """
        existing_shm = shm.SharedMemory(name=shm_name)

        with self:
            previous_checksum = None

            async for _ in self.async_pipe_reader_fifo(receiver):
                frame = np.array(existing_shm.buf, dtype=np.uint8).reshape(self.resolution)
                checksum = np.sum(frame)

                if checksum != previous_checksum:
                    previous_checksum = checksum
                    self._write(frame)

    @staticmethod
    @logger.contextualize(process="RECORDER")
    def recorder_process_context_manager(shm_name: str, receiver: PipeConnection) -> NoReturn: # pyright: ignore[reportReturnType]
        """
        Subproces entry point for recording video data from shared memory.
        """
        async def _run() -> NoReturn:
            recorder = Recorder()
            with recorder:
                await recorder.record(shm_name, receiver)

        try:
            asyncio.run(_run())
        except Exception as e:
            logger.critical(
                f"Recorder subprocess crashed: {type(e).__name__}: {e}", exc_info=True)
            raise
        except BaseException as e:
            # Catch segfaults and other non-Exception errors
            logger.critical(
                f"Recorder subprocess fatal error: {type(e).__name__}: {e}", exc_info=True)
            raise