"""Async Open Challenge vision processor.

Combines :class:`OpenChallengeVisionProcessor` with
:class:`AsyncMultiprocessingVisionProcessor` for subprocess-based
wall-distance measurement.
"""

from typing import Any

from piclient.core.vision.data import Walls

from .. import logger

from .open_challenge import OpenChallengeVisionProcessor
from .async_base import AsyncMultiprocessingVisionProcessor
from ..lib import GLOBAL_CONFIG, export

from multiprocessing import shared_memory
from multiprocessing.connection import PipeConnection

import numpy as np


@export
class OpenChallengeAsyncMultiprocessingVisionProcessor(OpenChallengeVisionProcessor, AsyncMultiprocessingVisionProcessor):
    """Async multiprocessing vision processor for the Open Challenge.

    Uses multiple inheritance to combine the Open Challenge wall-distance
    logic with async multiprocessing support.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialise via MRO, forwarding args to parent classes."""
        super(OpenChallengeAsyncMultiprocessingVisionProcessor,
              self).__init__(*args, **kwargs)

    async def get_normalized_relative_wall_distances_async(self, frame: np.ndarray) -> Walls:
        """Async wrapper around the synchronous wall-distance method.

        :param frame: Preprocessed HSV frame.
        :returns: Normalised wall distances.
        :rtype: Walls
        """
        return await self.loop.run_in_executor(self._executor, super(OpenChallengeAsyncMultiprocessingVisionProcessor, self).get_normalized_relative_wall_distances, frame)

    async def comprehensive_analysis(self, shm_name: str, receiver: PipeConnection, sender: PipeConnection) -> None:
        """Full async vision pipeline for the Open Challenge.

        Reads frames from shared memory, computes wall distances, and
        sends results through the multiprocessing pipe.

        :param shm_name: Name of the shared memory block.
        :param receiver: Pipe connection for frame-ready signals.
        :param sender: Pipe connection for sending results.
        """
        shm = None

        try:
            shm = shared_memory.SharedMemory(name=shm_name)
            if not shm or not shm.buf:
                raise RuntimeError("Failed to find Shared memory block")

            h: int = GLOBAL_CONFIG().CameraConfig.OUTPUT_HEIGHT
            w: int = GLOBAL_CONFIG().CameraConfig.OUTPUT_WIDTH
            c: int = GLOBAL_CONFIG().CameraConfig.OUTPUT_CHANNELS
            full_frame_size: int = h * w * c

            async for _ in OpenChallengeAsyncMultiprocessingVisionProcessor.async_pipe_reader(receiver):
                # Read the full raw frame from SHM then preprocess (which applies INITIAL_ROI)
                raw_frame: np.ndarray[tuple[int, ...], np.dtype[np.uint8]] = np.ndarray(
                    (h, w, c), dtype=np.uint8, buffer=shm.buf[:full_frame_size])
                frame: np.ndarray[tuple[int, ...],
                                  np.dtype[np.uint8]] = self._preprocess(raw_frame)
                walls: Walls = await self.get_normalized_relative_wall_distances_async(frame)

                await self.loop.run_in_executor(None, sender.send, walls)
        except (OSError, EOFError) as e:
            logger.info(
                f"Pipe broken or shared memory closed, shutting down vision processor: {e}")
        except Exception as e:
            logger.exception(f"Vision processor crashed unexpectedly: {e}")
        finally:
            shm.close() if shm else None
