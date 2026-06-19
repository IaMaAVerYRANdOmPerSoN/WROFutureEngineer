"""Base class for tuning/debugging tools.

Provides :class:`BaseTool` with shared-memory frame access, camera and
vision subprocess management, and drawing infrastructure.
"""

import asyncio
from multiprocessing.connection import Connection
import multiprocessing as mp
from multiprocessing import shared_memory
from utils import cv2, logger
from src.piclient.vision.async_base import AsyncMultiprocessingVisionProcessor
from src.piclient.vision.async_open import OpenChallengeAsyncMultiprocessingVisionProcessor
from src.piclient.lib.config import Config
import numpy as np


class BaseTool:
    """Base class for all tuning/debugging tools.

    Manages shared memory, camera subprocess, vision subprocesses (with
    and without perspective transform), and provides a drawing loop that
    displays frames in OpenCV windows.

    :ivar name: Tool name (used for window titles and shared memory).
    :ivar description: Human-readable description of the tool.
    :ivar frame: Current frame buffer (BGR, uint8).
    """

    def __init__(self, name, description):
        """Initialise the base tool.

        :param name: Tool name.
        :param description: Tool description.
        """
        self.name = name
        self.description = description
        self._created_windows: set[str] = set()
        self.frame = np.zeros((Config.CameraConfig.OUTPUT_HEIGHT - Config.CameraConfig.INITIAL_ROI,
                              Config.CameraConfig.OUTPUT_WIDTH, Config.CameraConfig.OUTPUT_CHANNELS), dtype=np.uint8)

    def _ensure_windows(self, *names):
        """Create and initialise OpenCV windows with a placeholder frame.

        :param names: Window names to create.
        """
        for name in names:
            cv2.namedWindow(name, cv2.WINDOW_NORMAL)

        placeholder = np.zeros_like(self.frame)
        for name in names:
            cv2.imshow(name, placeholder)

    def _draw_vision_object(self, object: VisionObject, color: tuple, frame):
        """Draw a single :class:`VisionObject` onto a frame.

        Draws the contour outline and a centroid circle. Validates frame
        shape to avoid crashes from shared-memory race conditions.

        :param object: The :class:`VisionObject` to draw.
        :param color: BGR colour tuple for the overlay.
        :param frame: Target frame (numpy array).
        """
        if not isinstance(frame, np.ndarray) or frame.shape != (Config.CameraConfig.OUTPUT_HEIGHT - Config.CameraConfig.INITIAL_ROI, Config.CameraConfig.OUTPUT_WIDTH, Config.CameraConfig.OUTPUT_CHANNELS,):
            logger.warning(
                "Frame may have been mishaped due to race condition on shared memory, skipping draw to avoid crash")
            return
        contour = object.contour
        if contour is not None:
            cv2.drawContours(frame, [contour], -1, color, 2)
            cv2.circle(frame, (int(object.x_centroid),
                       int(object.y_centroid)), 3, color, -1)

    def _vision_process_manager(self, shm_name: str, receiver: Connection, sender: Connection, **kwargs):
        """Subprocess target for perspective-transformed vision.

        :param shm_name: Shared memory block name.
        :param receiver: Pipe connection for frame-ready signals.
        :param sender: Pipe connection for vision results.
        """
        async def _run(*args, **kwargs):
            async with AsyncMultiprocessingVisionProcessor() as processor:
                await processor.comprehensive_analysis(shm_name, receiver, sender, *args, **kwargs)

        asyncio.run(_run())

    def _no_perspective_vision_process_manager(self, shm_name: str, receiver: Connection, sender: Connection, **kwargs):
        """Subprocess target for non-perspective vision (Open Challenge).

        :param shm_name: Shared memory block name.
        :param receiver: Pipe connection for frame-ready signals.
        :param sender: Pipe connection for vision results.
        """
        async def _run(*args, **kwargs):
            async with OpenChallengeAsyncMultiprocessingVisionProcessor() as processor:
                await processor.comprehensive_analysis(shm_name, receiver, sender, *args, **kwargs)

        asyncio.run(_run())

    def _camera_process_manager(self, shm_name: str, sender: Connection, *args, **kwargs):
        """Subprocess target for the camera stream.

        :param shm_name: Shared memory block name.
        :param sender: Pipe connection for frame-ready signals.
        """
        async def _run(*args, **kwargs):
            CameraClass = get_camera_class()
            async with CameraClass() as camera:
                await camera.stream(shm_name, sender, *args, **kwargs)

        asyncio.run(_run())

    def _draw(self, *args, **kwargs):
        """Draw the perspective-transformed view (abstract).

        Subclasses must override this method.

        :raises NotImplementedError: Always, unless overridden.
        """
        raise NotImplementedError("Subclasses must implement the _draw method")

    def _draw_no_perspective(self, *args, **kwargs):
        """Draw the raw (unwarped) view (abstract).

        Subclasses must override this method.

        :raises NotImplementedError: Always, unless overridden.
        """
        raise NotImplementedError(
            "Subclasses must implement the _draw_no_perspective method")

    async def run(self, *args, **kwargs):
        """Start the tool's main loop.

        Creates shared memory, spawns camera and vision subprocesses, and
        runs the drawing loop until the user presses ``q`` or ``Esc``.
        Cleans up subprocesses and shared memory on exit.
        """
        shm, camera_process, vision_process, no_perspective_vision_process = None, None, None, None
        shm_frame_bytes = (
            Config.CameraConfig.OUTPUT_WIDTH
            * (Config.CameraConfig.OUTPUT_HEIGHT - Config.CameraConfig.INITIAL_ROI)
            * Config.CameraConfig.OUTPUT_CHANNELS
        )

        try:
            logger.info(f"Running {self.name} tool...")

            try:
                shm = shared_memory.SharedMemory(
                    name=f"{self.name}_shm",
                    create=True,
                    size=shm_frame_bytes,
                )
            except FileExistsError:
                logger.warning(
                    f"Shared memory segment {self.name}_shm already exists, attempting to clean up and recreate...")
                try:
                    existing_shm = shared_memory.SharedMemory(
                        name=f"{self.name}_shm")
                    existing_shm.close()
                    existing_shm.unlink()
                    logger.info(
                        f"Cleaned up existing shared memory segment, retrying creation...")
                except Exception as e:
                    logger.error(
                        f"Failed to clean up existing shared memory segment: {e}")
                    raise RuntimeError(
                        f"Could not create shared memory segment for tool {self.name} and failed to clean up existing segment. Manual cleanup may be required. Original error: {e}")
                shm = shared_memory.SharedMemory(
                    name=f"{self.name}_shm",
                    create=True,
                    size=shm_frame_bytes,
                )

            camera_sender, camera_receiver = mp.Pipe()
            vision_sender, vision_receiver = mp.Pipe()
            no_perspective_camera_sender, no_perspective_camera_receiver = mp.Pipe()
            no_perspective_vision_sender, no_perspective_vision_receiver = mp.Pipe()

            camera_process = mp.Process(target=self._camera_process_manager, args=(
                shm.name, camera_sender, no_perspective_camera_sender))
            vision_process = mp.Process(target=self._vision_process_manager, args=(
                shm.name, camera_receiver, vision_sender))
            no_perspective_vision_process = mp.Process(target=self._no_perspective_vision_process_manager, args=(
                shm.name, no_perspective_camera_receiver, no_perspective_vision_sender))

            camera_process.start()
            vision_process.start()
            no_perspective_vision_process.start()

            if not camera_process.is_alive() or not vision_process.is_alive() or not no_perspective_vision_process.is_alive():
                logger.error(
                    "One or more processes failed to start correctly.")
                return

            vision_reader = AsyncMultiprocessingVisionProcessor.async_pipe_reader(
                vision_receiver)
            no_perspective_reader = AsyncMultiprocessingVisionProcessor.async_pipe_reader(
                no_perspective_vision_receiver)
            vision_iter = vision_reader.__aiter__()
            no_perspective_iter = no_perspective_reader.__aiter__()
            read_timeout = 1.0
            latest_data = None
            latest_no_perspective_data = None
            vision_task = asyncio.create_task(anext(vision_iter))
            no_perspective_task = asyncio.create_task(
                anext(no_perspective_iter))

            while True:
                try:
                    done, _ = await asyncio.wait(
                        {vision_task, no_perspective_task},
                        timeout=read_timeout,
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    if not done:
                        if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                            logger.info(
                                f"Tool {self.name} received close key, shutting down...")
                            break
                        raise asyncio.TimeoutError

                    for completed in done:
                        if completed is vision_task:
                            latest_data = completed.result()
                            vision_task = asyncio.create_task(
                                anext(vision_iter))
                        elif completed is no_perspective_task:
                            latest_no_perspective_data = completed.result()
                            no_perspective_task = asyncio.create_task(
                                anext(no_perspective_iter))

                    if latest_data is None or latest_no_perspective_data is None:
                        if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                            logger.info(
                                f"Tool {self.name} received close key, shutting down...")
                            break
                        continue
                except asyncio.TimeoutError:
                    process_states = {
                        "camera": camera_process.is_alive() if camera_process else False,
                        "vision": vision_process.is_alive() if vision_process else False,
                        "no_perspective_vision": no_perspective_vision_process.is_alive() if no_perspective_vision_process else False,
                    }
                    if not all(process_states.values()):
                        logger.error(
                            f"Tool {self.name} stalled and one or more child processes died: "
                            f"alive={process_states}, exitcodes="
                            f"camera={camera_process.exitcode if camera_process else None}, "
                            f"vision={vision_process.exitcode if vision_process else None}, "
                            f"no_perspective_vision={no_perspective_vision_process.exitcode if no_perspective_vision_process else None}"
                        )
                        break
                    continue
                except StopAsyncIteration:
                    logger.info(
                        f"No more data, terminating tool {self.name}...")
                    break
                self.frame = cv2.cvtColor(np.frombuffer(shm.buf, dtype=np.uint8)
                                          .reshape((
                                              Config.CameraConfig.OUTPUT_HEIGHT
                                              - Config.CameraConfig.INITIAL_ROI,
                                              Config.CameraConfig.OUTPUT_WIDTH,
                                              Config.CameraConfig.OUTPUT_CHANNELS,
                                              # Copy to avoid shared memory issues
                                          )), cv2.COLOR_BGR2RGB).copy()
                self._draw(latest_data, *args, **kwargs)
                self._draw_no_perspective(
                    latest_no_perspective_data, *args, **kwargs)
                if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                    logger.info(
                        f"Tool {self.name} received close key, shutting down...")
                    break
            for pending in (vision_task, no_perspective_task):
                if pending and not pending.done():
                    pending.cancel()
            await asyncio.gather(vision_task, no_perspective_task, return_exceptions=True)
        except asyncio.CancelledError:
            logger.info(
                f"Tool {self.name} shutting down. Press Ctrl+C again to skip graceful shutdown")
            raise
        finally:
            logger.info(
                "Terminating processes and destroying shared memory... ")
            try:
                cv2.destroyAllWindows()
                camera_process.terminate() if camera_process and camera_process.is_alive() else None
                vision_process.terminate() if vision_process and vision_process.is_alive() else None
                no_perspective_vision_process.terminate(
                ) if no_perspective_vision_process and no_perspective_vision_process.is_alive() else None
                camera_process.join(
                    timeout=1) if camera_process else None
                vision_process.join(
                    timeout=1) if vision_process else None
                no_perspective_vision_process.join(
                    timeout=1) if no_perspective_vision_process else None
                shm.close()
                shm.unlink()
                logger.info("Done")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
                logger.warning(
                    f"Leaked memory segments and processes may need to be cleaned up manually. Good luck finding them michael -_-")
