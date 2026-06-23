"""Asynchronous camera interface using picamera2.

Provides :class:`AsyncCamera`, a native async wrapper over the picamera2
library that supports non-blocking frame capture, shared memory streaming,
and subprocess-safe context management.
"""

from typing import Self
from ..lib import Config, export
from multiprocessing import shared_memory
import asyncio
from multiprocessing.connection import PipeConnection
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from .. import logger
from typing import Any

picamera2: Any = None

try:
    import picamera2  # pyright: ignore[reportMissingImports]
except ImportError:
    # Probably not on Pi
    logger.warning("picamera2 import failed, are you running on a Raspberry Pi? "
                   "Make sure include-system-site-packages=true in your environment. "
                   "If you are building documentation or testing on a different OS, you may ignore this message, "
                   "but some modules will not work as intended, and may raise exceptions.")


_CAM_DEFAULTS: Config.CameraConfig = Config.CameraConfig()


@export
class AsyncCamera:
    """
    A native python asynchronus wrapper over the picamera2.Picamera2 class

    :ivar config: Camera format configuration dict (default: ``CameraConfig.FORMAT``).
    :ivar sensor_config: Sensor mode configuration dict (default: ``CameraConfig.SENSOR_CONFIG``).
    :ivar controls_config: Camera controls configuration dict (default: ``CameraConfig.CONTROLS_CONFIG``).
    :ivar _cam: Internal picamera2.Picamera2 instance for frame capture, initilized to none and created by ``__aenter__``
    :ivar frame_width: Infered width of frame from configuration values
    :ivar frame_height: Infered height of frame from configuration values
    :ivar loop: Asyncio event loop to run capture coroutines
    :ivar _executor: Internal ``Concurent.futures.ThreadPoolExecutor`` created by __aenter__ for running synchronus picamera2 functions asynchronusly.

    """

    def __init__(
        self,
        config: dict[str, Any] = _CAM_DEFAULTS.FORMAT,
        sensor_config: dict[str, Any] = _CAM_DEFAULTS.SENSOR_CONFIG,
        controls_config: dict[str, Any] = _CAM_DEFAULTS.CONTROLS_CONFIG,
        executor_threads: int = _CAM_DEFAULTS.EXECUTOR_THREADS,
        max_concurrent_captures: int = _CAM_DEFAULTS.MAX_CONCURRENT_CAPTURES
    ):
        """Initialize the async camera wrapper.

        :param config: Camera format configuration dict (default: ``CameraConfig.FORMAT``).
        :param sensor_config: Sensor mode configuration dict (default: ``CameraConfig.SENSOR_CONFIG``).
        :param controls_config: Camera controls configuration dict (default: ``CameraConfig.CONTROLS_CONFIG``).
        :param executor_threads: The number of executor threads for the internal executor (default: ``CameraConfig.EXECUTOR_THREADS``)
        :param max_concurrent_captures: The maxmimum number of concurretn captures permitted by the internal semaphore (default: ``CameraConfig.MAX_CONCURRENT_CAPTURES``)
        """
        self.config: dict[str, Any] = config
        self.sensor_config: dict[str, Any] = sensor_config
        self.controls_config: dict[str, Any] = controls_config
        self.executor_threads = executor_threads
        self.max_concurrent_captures = max_concurrent_captures
        self._cam = None

        self.frame_width, self.frame_height = self.config["size"]

        try:
            self.loop = asyncio.get_event_loop()
        except RuntimeError:
            logger.warning(
                "No event loop currently running in thread, are you building docs?")

        self._executor = None

    async def __aenter__(self) -> Self:
        """
        Initializes hardware resources defined in __init__ asynchronously.

        :param self: The instance of `AsyncCamera`.
        :raises: `ConnectionError` if an exception occurs or the camera times out.

        :returns: `self`: the instance of `AsyncCamera`
        """
        self._executor = ThreadPoolExecutor(self.executor_threads)
        self._capture_semaphore = asyncio.Semaphore(
            self.max_concurrent_captures)

        try:
            self._cam = await asyncio.wait_for(
                self.loop.run_in_executor(self._executor, picamera2.Picamera2),
                timeout=Config.CameraConfig.HW_INIT_TIMEOUT
            )

            config = self._cam.create_preview_configuration(
                main=self.config,
                sensor=self.sensor_config,
                raw=None,
                controls=self.controls_config,
                buffer_count=Config.CameraConfig.BUFFER_COUNT,
            )

            await asyncio.wait_for(
                self.loop.run_in_executor(
                    self._executor, self._cam.configure, config),
                timeout=Config.CameraConfig.CONFIGURE_TIMEOUT
            )
            await asyncio.wait_for(
                self.loop.run_in_executor(self._executor, self._cam.start),
                timeout=Config.CameraConfig.START_TIMEOUT
            )

            logger.info(
                f"Camera configuration applied: {self._cam.camera_configuration()}")

            return self

        except (asyncio.TimeoutError, Exception) as e:
            logger.critical(f"Camera Hardware Initialization Failed: {e}")
            raise ConnectionError(
                "Camera not responding during power-up.") from e

    # Let the main loop handle the logging and execeptions
    async def __aexit__(self, *args: Any):
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

        Tears down existing hardware resources, reinitialises the camera
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

    async def get_frame_async(self, shm: shared_memory.SharedMemory | None = None, timeout: float = 0.1) -> None | np.ndarray:
        """
        Fetch a frame asynchronously from `self._cam`

        :param self: The instance of `AsyncCamera`
        :param timeout: The maximum roundtrip time, in seconds, before raising asyncio.TimeoutError
        :returns: *np.ndarray* an array representing the captured frame, determined by the format passed to the constructor.
        :raises: AttributeError when self._cam does is None, usually due to improper context management.
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

                if shm:
                    # Copy BGR888 data (H, W, 3) to shared buffer
                    shared_buffer = np.ndarray(
                        (self.frame_height, self.frame_width, 3), dtype=np.uint8, buffer=shm.buf)
                    np.copyto(shared_buffer, frame)

                    return
                else:
                    return frame.astype(np.uint8)

            except asyncio.TimeoutError as e:
                logger.warning(
                    f"Camera frame capture timed out ({e}), retrying...")
                # Give some grace
                await asyncio.sleep(Config.CameraConfig.CAPTURE_RETRY_SLEEP_SECONDS)

            except Exception as e:
                logger.warning(
                    f"Unexpected error during frame capture ({e}), continuing...")
                await asyncio.sleep(Config.CameraConfig.CAPTURE_ERROR_SLEEP_SECONDS)

    async def buffer_frames_async(self, num_frames: int = 5, timeout: float = 1.0):
        """
        Buffers `num_frames` frames asynchronously.

        :param self: The instance of `AysncCamera`.
        :param num_frames: The number of frames to buffer.
        :param timeout: Global timeout for buffering frames.
        :returns: `list[tuple[tuple[tuple[float, float, float]]]]`, where each element in the list represents a frame in YUV colorspace.
        """
        return [await asyncio.wait_for(self.get_frame_async(), timeout) for _ in range(num_frames)]

    async def stream(self, shm_name: str, sender: PipeConnection, *args: PipeConnection):
        """
        asynchronous indefinite yield camera IOstream.

        :param self: The instance of AsyncCamera.
        :yields: `tuple[tuple[tuple[float, float, float]]]`, an `vres * hres * 3` array representing the image in YUV colorspace.
        :returns: `None`
        """

        shm = None
        try:
            shm = shared_memory.SharedMemory(name=shm_name)
            while True:
                await self.get_frame_async(shm=shm)
                # Signal that a new frame is ready
                sender.send(True)
                if args:
                    for conn in args:
                        conn.send(True)
        finally:
            if shm:
                shm.close()

    @staticmethod
    def camera_process_context_manager(shm: str, sender: PipeConnection):
        """Subprocess entry point for streaming camera frames.

        Creates an :class:`AsyncCamera` instance within a fresh asyncio
        event loop and streams frames into the shared memory block named
        *shm*, signalling *sender* when each frame is ready.

        :param shm: Name of the shared memory block for frame data.
        :param sender: Multiprocessing :class:`Connection` used to signal new frames.
        """
        async def _run(shm: str, sender: PipeConnection):
            async with AsyncCamera() as camera:
                await camera.stream(shm, sender)

        asyncio.run(_run(shm, sender))
