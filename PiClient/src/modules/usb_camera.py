import asyncio
from multiprocessing.connection import Connection
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import os
import platform
from src import logger
import cv2
from multiprocessing import shared_memory
from src.modules.config import Config
from typing import Dict, Optional


os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")


class USBCamera:
    """
    USB camera adapter for Windows/development testing.
    Implements the same interface as AsyncCamera but uses OpenCV VideoCapture.
    """

    def __init__(
        self,
        camera_id: int = 0,
        config: Optional[Dict] = None,
        sensor_config: Optional[Dict] = None,
        controls_config: Optional[Dict] = None,
    ):
        """
        Initialize USB camera adapter.

        :param camera_id: USB camera device ID (0 for first camera, 1 for second, etc.)
        :param config: Camera configuration (uses Config.CameraConfig().FORMAT if None)
        """
        self._CONFIG: Dict = config if config else Config.CameraConfig().FORMAT
        self._SENSOR_CONFIG: Dict = sensor_config if sensor_config else {}
        self._CONTROLS_CONFIG: Dict = controls_config if controls_config else {}
        self._cam = None
        self._camera_id = camera_id

        self.FRAME_SIZE = self._CONFIG["size"]  # (height, width)
        self.loop = asyncio.get_event_loop()
        self.executor = None
        self.INITIAL_ROI = Config.CameraConfig().INITIAL_ROI

    def _get_backend_candidates(self) -> list[tuple[int, str]]:
        if platform.system() == "Windows":
            return [
                (cv2.CAP_ANY, "Auto"),
                (cv2.CAP_DSHOW, "DirectShow"),
            ]

        return [
            (cv2.CAP_ANY, "Auto"),
        ]

    async def __aenter__(self):
        """
        Initialize USB camera asynchronously.

        :raises: ConnectionError if camera cannot be opened
        :returns: self
        """
        self.executor = ThreadPoolExecutor(
            Config.CameraConfig.EXECUTOR_THREADS
        )
        self._capture_semaphore = asyncio.Semaphore(
            Config.CameraConfig.MAX_CONCURRENT_CAPTURES
        )

        def _init_camera():
            height, width = self.FRAME_SIZE

            for backend, backend_name in self._get_backend_candidates():
                cap = cv2.VideoCapture(self._camera_id, backend)
                if not cap.isOpened():
                    cap.release()
                    continue

                cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                cap.set(cv2.CAP_PROP_FPS, 30)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

                warmup_success = False
                for _ in range(5):
                    ret, _ = cap.read()
                    if ret:
                        warmup_success = True
                        break

                if not warmup_success:
                    logger.warning(
                        f"USB Camera backend {backend_name} opened but failed warmup reads; trying next backend"
                    )
                    cap.release()
                    continue

                actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                logger.info(
                    f"USB Camera opened with {backend_name}: requested {width}x{height}, "
                    f"got {actual_width}x{actual_height}"
                )

                return cap

            raise ConnectionError(
                f"Cannot open USB camera {self._camera_id} with any backend"
            )

        try:
            self._cam = await asyncio.wait_for(
                self.loop.run_in_executor(self.executor, _init_camera),
                timeout=Config.CameraConfig.HW_INIT_TIMEOUT,
            )

            logger.info(
                f"USB Camera {self._camera_id} initialized successfully"
            )
            return self

        except (asyncio.TimeoutError, Exception) as e:
            logger.critical(f"USB Camera initialization failed: {e}")
            raise ConnectionError(
                f"USB Camera {self._camera_id} not responding"
            ) from e

    async def __aexit__(self, *args):
        """Release camera resources."""
        if hasattr(self, "_cam") and self._cam:
            await self.loop.run_in_executor(self.executor, self._cam.release)
            self._cam = None

        if hasattr(self, "executor") and self.executor:
            self.executor.shutdown()

    def _bgr_to_yuv(self, bgr_frame: np.ndarray) -> np.ndarray:
        """
        Convert BGR frame from OpenCV to YUV format matching PiCamera output.

        :param bgr_frame: BGR frame from cv2.VideoCapture
        :returns: YUV frame as uint8 array
        """
        # OpenCV uses BGR, convert to YUV (same as PiCamera2 output)
        yuv_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2YUV)
        return yuv_frame

    async def get_frame_async(self, timeout: float = 0.1, shm_name: Optional[str] = None):
        """
        Fetch a frame asynchronously from USB camera.

        :param timeout: Maximum time to wait for frame
        :param shm_name: Shared memory name (optional)
        :returns: YUV frame with ROI applied, shape (height - INITIAL_ROI, width, 3)
        """
        shm = shared_memory.SharedMemory(name=shm_name) if shm_name else None

        while True:
            try:
                async with self._capture_semaphore:
                    # Capture frame in thread pool
                    def _capture():
                        ret, frame = self._cam.read()
                        if not ret:
                            raise RuntimeError(
                                "Failed to read frame from USB camera")
                        return frame

                    bgr_frame = await asyncio.wait_for(
                        self.loop.run_in_executor(self.executor, _capture),
                        timeout=timeout,
                    )

                # Convert BGR to YUV
                yuv_frame = self._bgr_to_yuv(bgr_frame)

                # Resize if camera doesn't match config exactly
                expected_height, expected_width = self.FRAME_SIZE
                if yuv_frame.shape[:2] != (expected_height, expected_width):
                    yuv_frame = cv2.resize(
                        yuv_frame,
                        (expected_width, expected_height),
                        interpolation=cv2.INTER_LINEAR,
                    )

                # Apply ROI cropping (same as AsyncCamera)
                yuv_frame = yuv_frame[self.INITIAL_ROI:, :, :]

                # Write to shared memory if requested
                if shm:
                    buffer = np.ndarray(
                        (expected_height - self.INITIAL_ROI, expected_width, 3),
                        dtype=np.uint8,
                        buffer=shm.buf,
                    )
                    np.copyto(buffer, yuv_frame)

                logger.info("Fetched new frame from USB camera successfully")
                return yuv_frame.astype(np.uint8)

            except asyncio.TimeoutError as e:
                logger.warning(
                    f"USB camera frame capture timed out ({e}), retrying...")
                await asyncio.sleep(Config.CameraConfig.CAPTURE_RETRY_SLEEP_SECONDS)

            except Exception as e:
                logger.warning(
                    f"Unexpected error during USB camera capture ({e}), continuing..."
                )
                await asyncio.sleep(Config.CameraConfig.CAPTURE_ERROR_SLEEP_SECONDS)

    async def buffer_frames_async(self, num_frames: int = 5, timeout: float = 1.0):
        """
        Buffer multiple frames asynchronously.

        :param num_frames: Number of frames to buffer
        :param timeout: Global timeout for buffering
        :returns: List of YUV frames
        """
        return [
            await asyncio.wait_for(self.get_frame_async(), timeout)
            for _ in range(num_frames)
        ]

    async def stream(self, shm_name: str, sender: Connection, *args: Connection):
        """
        Continuous frame streaming to shared memory with pipe signaling.

        :param shm_name: Shared memory segment name
        :param sender: Primary pipe to signal frame ready
        :param args: Additional pipes to signal
        """
        while True:
            await self.get_frame_async(shm_name=shm_name)
            # Signal that a new frame is ready
            sender.send(True)
            if args:
                for conn in args:
                    conn.send(True)
