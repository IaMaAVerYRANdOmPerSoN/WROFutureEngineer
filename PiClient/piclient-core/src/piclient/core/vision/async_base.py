"""Async multiprocessing vision base.

Provides :class:`AsyncMultiprocessingVisionProcessor`, which adds async
context management, pipe-based data reading, and subprocess scaffolding
to :class:`VisionProcessor`.
"""

from typing import Any, Self, NoReturn

import asyncio
from concurrent.futures import ThreadPoolExecutor
from multiprocessing.connection import Connection as PipeConnection

from loguru import logger
from ..lib import export
from ..utils import async_pipe_reader as utils_async_pipe_reader, async_pipe_reader_fifo as utils_async_pipe_reader_fifo
from .base import VisionProcessor


@export
class AsyncMultiprocessingVisionProcessor(VisionProcessor):
    """Async-capable vision processor with multiprocessing support.

    Wraps :class:`VisionProcessor` with a thread-pool executor and async
    context manager. Provides :meth:`async_pipe_reader` for consuming
    data from a multiprocessing :class:`Connection`.

    :ivar executor_size: Number of threads in the executor pool.
    :ivar executor: :class:`ThreadPoolExecutor` instance.
    :ivar loop: The asyncio event loop.
    """

    loop: asyncio.AbstractEventLoop
    async_pipe_reader = staticmethod(utils_async_pipe_reader)
    async_pipe_reader_fifo = staticmethod(utils_async_pipe_reader_fifo)

    def __init__(
        self,
        executor_size: int,
        loop: asyncio.AbstractEventLoop | None = None,
        *args: Any,
        **kwargs: Any
    ):
        """Initialise the async vision processor.

        :param executor_size: Number of threads for the executor pool.
        :param loop: Asyncio event loop (uses running loop if ``None``).
        """
        super(AsyncMultiprocessingVisionProcessor,
              self).__init__(*args, **kwargs)
        self.executor_size = executor_size
        self._executor = None
        try:
            self.loop = loop if loop else asyncio.get_running_loop()
        except RuntimeError:
            logger.warning(
                "No event loop currently running in thread, are you building docs?")

    async def __aenter__(self) -> Self:
        """Create the thread-pool executor on entry.

        :returns: ``self``
        """
        self._executor = ThreadPoolExecutor(self.executor_size)
        return self

    async def __aexit__(self, *args: Any, **kwargs: Any) -> None:
        """Shut down the thread-pool executor on exit."""
        if hasattr(self, "_executor") and self._executor:
            self._executor.shutdown()

    async def reload(self) -> Self:
        """Hot reload after changing attributes.

        Tears down existing hardware resources, reinitialises them
        with the updated configuration, and cleans up on failure before
        re-raising.

        ALWAYS call after changing attributes to reload internal context.
        Not doing so will lead to unpredictable behaviour.

        :returns: ``self``
        :raises Exception: Re-raises any exception during reload
        """
        await self.__aexit__()
        try:
            return await self.__aenter__()
        except Exception:
            await self.__aexit__()
            raise

    async def comprehensive_analysis(self, *args: Any, **kwargs: Any) -> NoReturn:
        """Run the full vision analysis pipeline (abstract).

        Subclasses must override this method.

        :raises NotImplementedError: Always, unless overridden.
        """
        raise NotImplementedError("Comprehensive analysis is abstract")

    @classmethod
    @logger.contextualize(process="VISION")
    def vision_process_context_manager(
        cls,
        shm: str,
        frame_receiver: PipeConnection,
        data_sender: PipeConnection,
        executor_size: int = 5,
        loop: asyncio.AbstractEventLoop | None = None
    ) -> NoReturn:  # pyright: ignore[reportReturnType]
        """Subprocess entry point for the vision pipeline.

        Creates an instance of this class, enters its async context,
        and runs :meth:`comprehensive_analysis`.

        :param shm: Name of the shared memory block for frame data.
        :param frame_receiver: Pipe connection to receive frame-ready signals.
        :param data_sender: Pipe connection to send vision results.
        :param executor_size: Thread-pool size.
        :param loop: Asyncio event loop (optional).
        """
        async def _run() -> NoReturn:
            if loop:
                async with cls(executor_size=executor_size, loop=loop) as vision:
                    await vision.comprehensive_analysis(shm, frame_receiver, data_sender)
            else:
                async with cls(executor_size=executor_size) as vision:
                    await vision.comprehensive_analysis(shm, frame_receiver, data_sender)
        try:
            asyncio.run(_run())
        except Exception as e:
            logger.critical(
                f"Vision subprocess crashed: {type(e).__name__}: {e}", exc_info=True)
            raise
        except BaseException as e:
            # Catch segfaults and other non-Exception errors
            logger.critical(
                f"Vision subprocess fatal error: {type(e).__name__}: {e}", exc_info=True)
            raise
