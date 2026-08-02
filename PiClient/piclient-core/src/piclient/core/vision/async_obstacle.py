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
from .data import WallsAndObstacles
from .obstacle_challenge import ObstacleChallengeVisionProcessor


@export
class ObstacleChallengeAsyncMultiprocessingVisionProcessor(ObstacleChallengeVisionProcessor, AsyncMultiprocessingVisionProcessor):
    """Async multiprocessing vision processor for the Obstacle Challenge.

    Uses multiple inheritance to combine the Obstacle Challenge wall-distance
    logic with async multiprocessing support.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialise via MRO, forwarding args to parent classes."""
        super(ObstacleChallengeAsyncMultiprocessingVisionProcessor,
              self).__init__(*args, **kwargs)

    async def get_walls_and_obstacles_async(self, frame: np.ndarray) -> WallsAndObstacles:
        """Async wrapper around the synchronous wall-distance and obstacle detection method.

        :param frame: Preprocessed HSV frame.
        :returns: Normalised wall distances and obstacle information.
        :rtype: WallsAndObstacles
        """
        return await self.loop.run_in_executor(self._executor, super(ObstacleChallengeAsyncMultiprocessingVisionProcessor, self).get_walls_and_obstacles, frame)

    async def get_target_async(self, walls_and_obstacles: WallsAndObstacles) -> tuple[int, int] | None:
        """Async wrapper around the synchronous target computation method.

        :param walls_and_obstacles: Walls and obstacles data.
        :returns: Target point as (x, y) tuple.
        """
        return await self.loop.run_in_executor(self._executor, super(ObstacleChallengeAsyncMultiprocessingVisionProcessor, self).get_target, walls_and_obstacles)
    
    async def comprehensive_analysis(
        self,
        shm_name: str,
        receiver: PipeConnection,
        sender: PipeConnection,
        ) -> NoReturn: # pyright: ignore[reportReturnType]
        """Full async vision pipeline for the Obstacle Challenge.

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

            async for _ in ObstacleChallengeAsyncMultiprocessingVisionProcessor.async_pipe_reader(receiver):
                # Read the cropped frame from SHM then preprocess it.
                raw_frame: np.ndarray[tuple[int, ...], np.dtype[np.uint8]] = np.ndarray(
                    (h, w, c), dtype=np.uint8, buffer=shm.buf)
                frame: np.ndarray[tuple[int, ...],
                                  np.dtype[np.uint8]] = self._preprocess(raw_frame)

                walls_and_obstacles: WallsAndObstacles = await self.get_walls_and_obstacles_async(frame)
                target_point = await self.get_target_async(walls_and_obstacles)

                data = (walls_and_obstacles, target_point)
                sender.send(data)
        except (OSError, EOFError) as e:
            logger.info(
                f"Pipe broken or shared memory closed, shutting down vision processor: {e}")
        except Exception as e:
            logger.critical(f"Vision processor crashed unexpectedly")
            logger.exception(e)
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
