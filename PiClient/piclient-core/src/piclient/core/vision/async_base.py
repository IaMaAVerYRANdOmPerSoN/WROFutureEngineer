"""Async multiprocessing vision base.

Provides :class:`AsyncMultiprocessingVisionProcessor`, which adds async
context management, pipe-based data reading, and subprocess scaffolding
to :class:`VisionProcessor`.
"""

from .. import logger
from .base import VisionProcessor
from ..lib import export
import asyncio
from concurrent.futures import ThreadPoolExecutor
from collections import deque
from multiprocessing.connection import PipeConnection
from typing import Any, Self


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
            self.loop = loop if loop else asyncio.get_event_loop
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

    async def comprehensive_analysis(self, *args: Any, **kwargs: Any) -> None:
        """Run the full vision analysis pipeline (abstract).

        Subclasses must override this method.

        :raises NotImplementedError: Always, unless overridden.
        """
        raise NotImplementedError("Comprehensive analysis is abstract")

    @staticmethod
    async def async_pipe_reader(receiver: PipeConnection):
        """Async generator that yields data from a multiprocessing pipe.

        On Linux, uses ``loop.add_reader`` for efficient event-driven
        consumption with a deque cache. Falls back to polling on Windows.

        :param receiver: Multiprocessing :class:`Connection` to read from.
        :yields: Objects received from the pipe (LIFO order).
        """
        loop = asyncio.get_event_loop()
        local_cache: deque[Any] = deque(maxlen=3)

        try:
            data_event = asyncio.Event()

            def yielder():
                data_event.set()

            loop.add_reader(receiver.fileno(), yielder)

            try:
                while True:
                    await data_event.wait()

                    while receiver.poll():
                        local_cache.append(await loop.run_in_executor(None, receiver.recv))

                    for _ in range(len(local_cache)):
                        yield local_cache.pop()  # Last In First Out

                    data_event.clear()
            finally:
                loop.remove_reader(receiver.fileno())
        except NotImplementedError:  # Windows doesn't support file descriptors
            while True:
                try:
                    data = await loop.run_in_executor(None, receiver.recv)
                except (EOFError, OSError):
                    break
                yield data

    @classmethod
    def vision_process_context_manager(
        cls,
        shm: str,
        frameReceiver: PipeConnection,
        data_sender: PipeConnection,
        executor_size: int = 5,
        loop: asyncio.AbstractEventLoop | None = None
    ):
        """Subprocess entry point for the vision pipeline.

        Creates an instance of this class, enters its async context,
        and runs :meth:`comprehensive_analysis`.

        :param shm: Name of the shared memory block for frame data.
        :param frameReceiver: Pipe connection to receive frame-ready signals.
        :param data_sender: Pipe connection to send vision results.
        :param executor_size: Thread-pool size.
        :param loop: Asyncio event loop (optional).
        """
        async def _run():
            if loop:
                async with cls(executor_size, loop) as vision:
                    await vision.comprehensive_analysis(shm, frameReceiver, data_sender)
            else:
                async with cls(executor_size) as vision:
                    await vision.comprehensive_analysis(shm, frameReceiver, data_sender)
        asyncio.run(_run())
