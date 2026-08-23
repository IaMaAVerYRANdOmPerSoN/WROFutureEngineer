"""
Provides class`Recorder`, which writes recorded test data from shm to disk.
"""

from typing import Self, NoReturn
from types import FrameType, TracebackType

import asyncio
import time
import signal
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
    """Record camera frames from shared memory into an MP4 video.

    The recorder consumes frame-ready notifications from a multiprocessing
    pipe, skips frames whose checksum has not changed, and writes distinct
    timestamped files below ``WRO_recordings``.

    :ivar resolution: Frame shape as ``(height, width, channels)``.
    :ivar fps: Output video frame rate.
    :ivar writer: OpenCV writer used for the output file.
    :ivar timestamp: Unix timestamp assigned when recording starts.
    """

    _DEFAULT_RESOLUTION: tuple[int, int, int] = GLOBAL_CONFIG().CameraConfig.OUTPUT_SHAPE
    _DEFAULT_FPS: float = GLOBAL_CONFIG().CameraConfig.FPS
    async_pipe_reader = staticmethod(utils_async_pipe_reader)
    async_pipe_reader_fifo = staticmethod(utils_async_pipe_reader_fifo)

    def __init__(self, writer: cv2.VideoWriter=cv2.VideoWriter(), resolution: tuple[int, int] | None=None, fps: float | None = None) -> None:
        """Initialize a recorder with an OpenCV writer and output settings.

        :param writer: OpenCV video writer to open and populate on context
            entry.
        :param resolution: Output frame dimensions as ``(height, width)``;
            defaults to the configured camera shape.
        :param fps: Output frame rate; defaults to camera configuration.
        :returns: ``None``.
        :rtype: None
        """
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
        self.fourcc = self.writer.fourcc(*"mp4v")

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
        frame_size = (self.resolution[1], self.resolution[0])
        self.writer.open(
            f"WRO_recordings/recording_{int(self.timestamp)}.mp4",
            self.fourcc,
            self.fps,
            frame_size
        )
        if not self.writer.isOpened():
            raise RuntimeError("Failed to open VideoWriter.")
        return self

    def __exit__(self, exc_type: type[BaseException], exc_value: BaseException, traceback: TracebackType) -> None:
        """Exit the context manager and release the video writer."""
        self.writer.release()
        
    async def record(self, shm_name: str, receiver: PipeConnection) -> NoReturn: # pyright: ignore[reportReturnType]
        """Read frame notifications and write changed shared-memory frames.

        :param shm_name: Name of the shared-memory segment containing frames.
        :param receiver: Pipe connection that signals when a frame is ready.
        :returns: Never returns during normal recording; cancellation or a
            pipe error ends the loop.
        :rtype: NoReturn
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
    @logger.catch
    def recorder_process_context_manager(shm_name: str, receiver: PipeConnection) -> NoReturn: # pyright: ignore[reportReturnType]
        """Run :meth:`record` as a signal-aware recorder subprocess.

        :param shm_name: Name of the shared-memory segment containing frames.
        :param receiver: Pipe connection that signals frame availability.
        :returns: Never returns while recording normally.
        :rtype: NoReturn
        """
        def _intercept_signal(signum: int, frame: FrameType | None) -> None:
            """Convert a termination signal into the recorder's shutdown path.

            :param signum: Operating-system signal number received.
            :param frame: Current Python stack frame, if supplied by the signal
                machinery.
            :raises KeyboardInterrupt: Always, to stop the recorder loop.
            """
            logger.info(f"Stopping recorder subprocess...")
            raise KeyboardInterrupt

        signal.signal(signal.SIGINT, _intercept_signal)
        signal.signal(signal.SIGTERM, _intercept_signal)

        async def _run() -> NoReturn:
            """Create a recorder and run it until cancellation or shutdown."""
            recorder = Recorder()
            await recorder.record(shm_name, receiver)

        try:
            asyncio.run(_run())
        except KeyboardInterrupt:
            logger.info("Shutting down recorder subprocess...")
        except Exception as e:
            logger.critical(
                f"Recorder subprocess crashed: {type(e).__name__}: {e}", exc_info=True)
            raise
        except BaseException as e:
            # Catch segfaults and other non-Exception errors
            logger.critical(
                f"Recorder subprocess fatal error: {type(e).__name__}: {e}", exc_info=True)
            raise