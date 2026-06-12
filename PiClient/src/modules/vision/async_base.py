"""Async multiprocessing vision base.

Provides :class:`AsyncMultiprocessingVisionProcessor`, which adds async
context management, pipe-based data reading, and subprocess scaffolding
to :class:`VisionProcessor`.
"""

from src.modules.vision.base import VisionProcessor
import asyncio
from concurrent.futures import ThreadPoolExecutor
from collections import deque
from multiprocessing.connection import Connection

class AsyncMultiprocessingVisionProcessor(VisionProcessor):
    """Async-capable vision processor with multiprocessing support.

    Wraps :class:`VisionProcessor` with a thread-pool executor and async
    context manager. Provides :meth:`async_pipe_reader` for consuming
    data from a multiprocessing :class:`Connection`.

    :ivar executor_size: Number of threads in the executor pool.
    :ivar executor: :class:`ThreadPoolExecutor` instance.
    :ivar loop: The asyncio event loop.
    """
    def __init__(self, executor_size, loop, *args, **kwargs):
        """Initialise the async vision processor.

        :param executor_size: Number of threads for the executor pool.
        :param loop: Asyncio event loop (uses running loop if ``None``).
        """
        super(AsyncMultiprocessingVisionProcessor,
              self).__init__(*args, **kwargs)
        self.executor_size = executor_size
        self.executor = None
        self.loop = loop if loop else asyncio.get_event_loop()

    async def __aenter__(self):
        """Create the thread-pool executor on entry.

        :returns: ``self``
        """
        self.executor = ThreadPoolExecutor(self.executor_size) 
        return self

    async def __aexit__(self, *args, **kwargs):
        """Shut down the thread-pool executor on exit."""
        if hasattr(self, "executor") and self.executor:
            self.executor.shutdown()

    async def comprehensive_analysis(self, *args, **kwargs):
        """Run the full vision analysis pipeline (abstract).

        Subclasses must override this method.

        :raises NotImplementedError: Always, unless overridden.
        """
        raise NotImplementedError("Comprehensive analysis is abstract")

    @staticmethod
    async def async_pipe_reader(receiver: Connection):
        """Async generator that yields data from a multiprocessing pipe.

        On Linux, uses ``loop.add_reader`` for efficient event-driven
        consumption with a deque cache. Falls back to polling on Windows.

        :param receiver: Multiprocessing :class:`Connection` to read from.
        :yields: Objects received from the pipe (LIFO order).
        """
        loop = asyncio.get_running_loop()
        local_cache = deque(maxlen=3)

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
                        yield local_cache.pop() # Last In First Out

                    data_event.clear()
            finally:
                loop.remove_reader(receiver.fileno())
        except NotImplementedError: # Windows doesn't support file descriptors
            while True: 
                try:
                    data = await loop.run_in_executor(None, receiver.recv)
                except (EOFError, OSError):
                    break
                yield data

    @classmethod
    def vision_process_context_manager(cls, shm, frameReceiver: Connection, data_sender: Connection, executor_size = 5, loop: asyncio.EventLoop | None = None):
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
            async with cls(executor_size, loop) as vision:
                await vision.comprehensive_analysis(shm, frameReceiver, data_sender)
        asyncio.run(_run())