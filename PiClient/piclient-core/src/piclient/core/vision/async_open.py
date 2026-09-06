"""Async Open Challenge vision processor.

Combines :class:`OpenChallengeVisionProcessor` with
:class:`AsyncMultiprocessingVisionProcessor` for subprocess-based
wall-distance measurement.
"""

from typing import Any, NoReturn

from multiprocessing import shared_memory
from multiprocessing.connection import Connection as PipeConnection

import numpy as np

from loguru import logger

from ..lib import GLOBAL_CONFIG, export
from .async_base import AsyncMultiprocessingVisionProcessor
from .data import Walls
from .open_challenge import OpenChallengeVisionProcessor


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

    async def comprehensive_analysis(
        self,
        shm_name: str,
        receiver: PipeConnection,
        sender: PipeConnection
    ) -> NoReturn:  # pyright: ignore[reportReturnType] STFU
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

            h, w, c = GLOBAL_CONFIG().CameraConfig.OUTPUT_SHAPE

            async for _ in OpenChallengeAsyncMultiprocessingVisionProcessor.async_pipe_reader(receiver):
                # Read the cropped frame from SHM then preprocess it.
                raw_frame: np.ndarray[tuple[int, ...], np.dtype[np.uint8]] = np.ndarray(
                    (h, w, c), dtype=np.uint8, buffer=shm.buf)
                frame: np.ndarray[tuple[int, ...],
                                  np.dtype[np.uint8]] = self._preprocess(raw_frame)
                walls: Walls = await self.get_normalized_relative_wall_distances_async(frame)

                sender.send(walls)
        except (OSError, EOFError) as e:
            logger.info(
                f"Pipe broken or shared memory closed, shutting down vision processor: {e}")
        except Exception as e:
            logger.critical(f"Vision processor crashed unexpectedly")
            raise # To logger.catch(reraise=True) in the runner
        finally:
            try:
                receiver.close()
            except Exception:
                pass
            try:
                sender.close()
            except Exception:
                pass
            shm.close() if shm else None
