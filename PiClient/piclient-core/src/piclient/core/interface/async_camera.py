"""Asynchronous camera interface using picamera2.

Provides :class:`AsyncCamera`, a native async wrapper over the picamera2
library that supports non-blocking frame capture, shared memory streaming,
and subprocess-safe context management.
"""

from typing import Any, NoReturn, Self

import asyncio
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import shared_memory
from multiprocessing.connection import Connection as PipeConnection

import numpy as np
from loguru import logger

from ..lib import GLOBAL_CONFIG
from ..lib.exporter import export


picamera2: Any = None

try:
    # pyright: ignore[reportMissingImports, reportMissingTypeStubs]
    import picamera2
except ImportError:
    # Probably not on Pi
    logger.warning("picamera2 import failed, are you running on a Raspberry Pi? "
                   "Make sure include-system-site-packages=true in your environment. "
                   "If you are building documentation or testing on a different OS, you may ignore this message, "
                   "but some modules will not work as intended, and may raise exceptions.")


_CAM_DEFAULTS = GLOBAL_CONFIG().CameraConfig


def _slice_length(axis: slice, total: int) -> int:
    """Return the number of positions selected on one camera axis.

    Missing slice bounds are replaced with the corresponding edge of the
    complete camera dimension.

    :param axis: Slice selecting part of one camera dimension.
    :param total: Full size of that dimension.
    :returns: Number of selected positions.
    :rtype: int
    """
    start = 0 if axis.start is None else axis.start
    stop = total if axis.stop is None else axis.stop
    return stop - start


@export
class AsyncCamera:
    """
    A native Python asynchronous wrapper over :class:`picamera2.Picamera2`.

    :ivar config: Camera format configuration dictionary, defaulting to
        ``GLOBAL_CONFIG().CameraConfig.FORMAT``.
    :ivar sensor_config: Sensor mode configuration dictionary, defaulting to
        ``GLOBAL_CONFIG().CameraConfig.SENSOR_CONFIG``.
    :ivar controls_config: Camera controls dictionary, defaulting to
        ``GLOBAL_CONFIG().CameraConfig.CONTROLS_CONFIG``.
    :ivar _cam: Internal :class:`picamera2.Picamera2` instance, initialized by
        :meth:`__aenter__` and ``None`` before entry.
    :ivar frame_width: Cropped frame width in pixels, derived from ``size`` and
        the second ROI slice.
    :ivar frame_height: Cropped frame height in pixels, derived from ``size``
        and the first ROI slice.
    :ivar loop: Asyncio event loop to run capture coroutines
    :ivar _executor: Internal :class:`concurrent.futures.ThreadPoolExecutor`
        created by :meth:`__aenter__` for running blocking camera calls.

    """

    def __init__(
        self,
        config: dict[str, Any] = _CAM_DEFAULTS.FORMAT,
        sensor_config: dict[str, Any] = _CAM_DEFAULTS.SENSOR_CONFIG,
        controls_config: dict[str, Any] = _CAM_DEFAULTS.CONTROLS_CONFIG,
        initial_roi: tuple[slice, slice, slice] = _CAM_DEFAULTS.INITIAL_ROI,
        executor_threads: int = _CAM_DEFAULTS.EXECUTOR_THREADS,
        max_concurrent_captures: int = _CAM_DEFAULTS.MAX_CONCURRENT_CAPTURES
    ) -> None:
        """Initialize the async camera wrapper.

        :param config: Picamera2 format dictionary, defaulting to
            ``GLOBAL_CONFIG().CameraConfig.FORMAT``.
        :param sensor_config: Sensor mode dictionary, defaulting to the global
            camera configuration.
        :param controls_config: Picamera2 controls dictionary, defaulting to
            the global camera configuration.
        :param initial_roi: Three-dimensional ``(rows, columns, channels)``
            crop applied after capture.
        :param executor_threads: Number of threads for blocking camera calls.
        :param max_concurrent_captures: Maximum simultaneous capture calls.
        """
        self.config: dict[str, Any] = config
        self.sensor_config: dict[str, Any] = sensor_config
        self.controls_config: dict[str, Any] = controls_config
        self.initial_roi: tuple[slice, slice, slice] = initial_roi
        self.executor_threads: int = executor_threads
        self.max_concurrent_captures: int = max_concurrent_captures
        self._cam = None

        capture_width, capture_height = self.config["size"]
        self.frame_width = _slice_length(self.initial_roi[1], capture_width)
        self.frame_height = _slice_length(self.initial_roi[0], capture_height)

        try:
            self.loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning(
                "No event loop currently running in thread, are you building docs?")

        self._executor = None

    async def __aenter__(self) -> Self:
        """
        Initialize the configured camera hardware asynchronously.

        :raises ConnectionError: If initialization fails or the camera times
            out.

        :returns: This initialized :class:`AsyncCamera` instance.
        :rtype: AsyncCamera
        """
        self._executor = ThreadPoolExecutor(self.executor_threads)
        self._capture_semaphore = asyncio.Semaphore(
            self.max_concurrent_captures)

        try:
            self._cam = await asyncio.wait_for(
                self.loop.run_in_executor(self._executor, picamera2.Picamera2),
                timeout=GLOBAL_CONFIG().CameraConfig.HW_INIT_TIMEOUT
            )

            config = self._cam.create_preview_configuration(
                main=self.config,
                sensor=self.sensor_config,
                raw=None,
                controls=self.controls_config,
                buffer_count=GLOBAL_CONFIG().CameraConfig.BUFFER_COUNT,
            )

            await asyncio.wait_for(
                self.loop.run_in_executor(
                    self._executor, self._cam.configure, config),
                timeout=GLOBAL_CONFIG().CameraConfig.CONFIGURE_TIMEOUT
            )
            await asyncio.wait_for(
                self.loop.run_in_executor(self._executor, self._cam.start),
                timeout=GLOBAL_CONFIG().CameraConfig.START_TIMEOUT
            )

            logger.info(
                f"Camera configuration applied: {self._cam.camera_configuration()}")

            return self

        except (asyncio.TimeoutError, Exception) as e:
            logger.critical(f"Camera Hardware Initialization Failed: {e}")
            raise ConnectionError(
                "Camera not responding during power-up.") from e

    async def __aexit__(self, *args: Any) -> None:
        """Tear down camera hardware resources asynchronously.

        Stops the camera, closes the device, and shuts down the thread pool
        executor. Exceptions during cleanup are intentionally not raised so
        the main loop can handle logging.
        """
        if hasattr(self, "_cam") and self._cam:
            await self.loop.run_in_executor(self._executor, self._cam.stop)
            await self.loop.run_in_executor(self._executor, self._cam.close)
            self._cam = None

        if hasattr(self, "_executor") and self._executor:
            self._executor.shutdown()

    async def reload(self) -> Self:
        """Hot reload after changing attributes.

        Tears down existing hardware resources and reinitializes the camera
        with the updated configuration, and cleans up on failure before
        re-raising.

        ALWAYS call after changing attributes to reload internal context.
        Not doing so will lead to unpredictable behaviour.

        :returns: This reinitialized :class:`AsyncCamera` instance.
        :rtype: AsyncCamera
        :raises Exception: Re-raises any exception during reload
        """
        await self.__aexit__()
        try:
            return await self.__aenter__()
        except Exception:
            await self.__aexit__()
            raise

    async def get_frame_async(self, shm: shared_memory.SharedMemory | None = None, timeout: float = 0.1) -> None | np.ndarray[tuple[int, int, int], np.dtype[np.uint8]]:
        """
        Fetch one frame asynchronously from the configured camera.

        :param shm: Optional shared-memory destination. When supplied, the
            cropped frame is copied there and ``None`` is returned.
        :param timeout: Maximum time in seconds for one underlying capture;
            capture timeouts and other capture errors are retried indefinitely.
        :returns: The cropped ``uint8`` frame when *shm* is not supplied;
            otherwise ``None``.
        :rtype: numpy.ndarray or None
        :raises AttributeError: If the camera context has not been entered.
        :raises ValueError: If *shm* is too small for the cropped frame.
        """

        while True:
            if not self._cam:
                raise AttributeError(
                    "Please Use the AysncCamera's aysnc context manager to initilize hardware resources before perfoming any operations.")

            try:
                async with self._capture_semaphore:
                    # type: ignore
                    frame: np.ndarray = await asyncio.wait_for(
                        self.loop.run_in_executor(
                            self._executor, self._cam.capture_array),
                        timeout=timeout,
                    )

                frame = frame[self.initial_roi]

                if shm:
                    # Copy cropped BGR888 data (H, W, 3) to shared buffer
                    shared_buffer: np.ndarray[tuple[int, ...], np.dtype[np.uint8]] = np.ndarray(
                        (self.frame_height, self.frame_width, 3), dtype=np.uint8, buffer=shm.buf)
                    np.copyto(shared_buffer, frame)

                    return
                else:
                    return frame.astype(np.uint8)

            except asyncio.TimeoutError as e:
                logger.warning(
                    f"Camera frame capture timed out ({e}), retrying...")
                # Give some grace
                await asyncio.sleep(GLOBAL_CONFIG().CameraConfig.CAPTURE_RETRY_SLEEP_SECONDS)

            except Exception as e:
                logger.warning(
                    f"Unexpected error during frame capture ({e}), continuing...")
                await asyncio.sleep(GLOBAL_CONFIG().CameraConfig.CAPTURE_ERROR_SLEEP_SECONDS)

    async def buffer_frames_async(self, num_frames: int = 5, timeout: float = 1.0) -> list[np.ndarray[tuple[int, ...], np.dtype[np.uint8]] | None]:
        """
        Buffer *num_frames* frames asynchronously.

        :param num_frames: Number of frames to capture.
        :param timeout: Maximum time in seconds allowed for each capture.
            The outer ``asyncio.wait_for`` can raise ``TimeoutError`` even
            though :meth:`get_frame_async` retries internally.
        :returns: List of captured ``uint8`` frames; a frame is ``None`` only
            when the underlying capture method returns no array.
        :rtype: list[numpy.ndarray | None]
        """
        return [await asyncio.wait_for(self.get_frame_async(), timeout) for _ in range(num_frames)]

    async def stream(self, shm_name: str, *senders: PipeConnection) -> NoReturn:
        """
        Asynchronous indefinite yield camera IOstream.

        :param shm_name: Name of the shared-memory block receiving frames.
        :param senders: Pipe connections notified after each captured frame.
        Each captured frame is copied into the named shared-memory block and
        ``True`` is sent through every supplied pipe. The shared-memory handle
        is closed when the coroutine exits; the block itself is not unlinked.

        :yields: No values; this coroutine runs until cancelled or until an
            unrecoverable capture error occurs.
        :rtype: NoReturn
        """

        shm = None
        try:
            shm = shared_memory.SharedMemory(name=shm_name)
            while True:
                await self.get_frame_async(shm=shm)
                # Signal that a new frame is ready
                for conn in senders:
                    conn.send(True)

        finally:
            if shm:
                shm.close()

    @staticmethod
    @logger.contextualize(process="CAMERA")
    def camera_process_context_manager(shm: str, *senders: PipeConnection) -> NoReturn: # pyright: ignore[reportReturnType]
        """Subprocess entry point for streaming camera frames.

        Creates an :class:`AsyncCamera` instance within a fresh asyncio
        event loop and streams frames into the shared memory block named
        *shm*, signalling *senders* when each frame is ready.

        :param shm: Name of the shared memory block for frame data.
        :param senders: Multiprocessing :class:`Connection` objects used to signal new frames.
        """
        async def _run(shm: str, *senders: PipeConnection) -> NoReturn:
            """Create a camera in the child event loop and stream frames."""
            async with AsyncCamera() as camera:
                # NoReturn implies _run is NoReturn
                await camera.stream(shm, *senders)

        # calling _run here implies the whole function is NoReturn (asyncio.run essentially awaits the coroutine but from a sync caller)
        try:
            asyncio.run(_run(shm, *senders))
        except Exception as e:
            logger.critical(
                f"Camera subprocess crashed: {type(e).__name__}: {e}", exc_info=True)
            raise
        except BaseException as e:
            # Catch segfaults and other non-Exception errors
            logger.critical(
                f"Camera subprocess fatal error: {type(e).__name__}: {e}", exc_info=True)
            raise
