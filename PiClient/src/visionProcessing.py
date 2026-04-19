from logging import config
from multiprocessing.connection import Connection
import cv2
import numpy as np
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, NoReturn, Sequence, Tuple, Literal, List
from itertools import cycle
from loguru import logger
from multiprocessing import shared_memory
from dataclasses import dataclass
from statistics import mean
from scipy.interpolate import CubicSpline
from src.config import Config


@dataclass
class VisionObject():
    contour: np.ndarray
    color: str

    def __post_init__(self):
        self.bbox: tuple[float, float, float,
                         float] = cv2.boundingRect(self.contour)
        x, y, w, h = self.bbox
        self.x_centroid: float = x + w/2
        self.y_centroid: float = y + h/2
        # Bottom y deprecated because perspective transform makes everything top-down


class VisionProcessor():
    PERSPECTIVE_TRANSFORM = np.array(
        (Config.VisionConfig.PERSPECTIVE_TRANSFORM), dtype=np.float32)

    def __init__(self):
        # I will add autotuning soonTM lol so yes these are instance variables, not class variables
        self.lower_orange = Config.VisionConfig.LOWER_ORANGE
        self.upper_orange = Config.VisionConfig.UPPER_ORANGE

        self.lower_blue = Config.VisionConfig.LOWER_BLUE
        self.upper_blue = Config.VisionConfig.UPPER_BLUE

        self.lower_green = Config.VisionConfig.LOWER_GREEN
        self.upper_green = Config.VisionConfig.UPPER_GREEN

        self.lower_red = Config.VisionConfig.LOWER_RED
        self.upper_red = Config.VisionConfig.UPPER_RED

        # Stateful obstacle trajectory approximation used by obstacle challenge.
        self._obstacle_path_frame_modulo = cycle(range(5))
        self._obstacle_path_spline = None
        self._obstacle_last_y = None

    # Applying cv2.perspectiveTransform is much more efficient than warping whole frame
    def _perspective_transform(self, contours: np.ndarray, colors: Sequence[str]) -> np.ndarray[VisionObject]:
        contours = np.array([VisionObject(contour=cv2.perspectiveTransform(
            contour, VisionProcessor.PERSPECTIVE_TRANSFORM), color=color) for contour, color in zip(contours, colors)])
        return contours

    def _find_blocks(self, masks, colors):
        contours = []
        detected_colors = []

        for mask, color in zip(masks, colors):
            detected_contours, * \
                _ = cv2.findContours(
                    mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if detected_contours:
                contours.extend(detected_contours)
                detected_colors.extend([color] * len(detected_contours))

        if not contours:
            return tuple()

        contours.sort(key=lambda i: cv2.contourArea(i), reverse=True)
        contours = np.array(contours, dtype=np.float32)

        logger.info(f"Detected {len(contours)} objects.")
        return self._perspective_transform(contours, detected_colors)
        # Okay so I this is a pragmatic solution because I only have to change a single method to apply perspective transforms globally. Also way faster then warping whole frame.

    def find_obstacles(self, frame):
        logger.info("Searching for traffic signs...")
        uv = frame[:, :, 1:3]
        green_mask = cv2.inRange(uv, self.LOWER_GREEN, self.UPPER_GREEN)
        red_mask = cv2.inRange(uv, self.LOWER_RED, self.UPPER_RED)

        return self._find_blocks([green_mask, red_mask], ["green", "red"])

    def check_corner_lines(self, frame):
        logger.info("Searching for turn aids...")
        uv = frame[:, :, 1:3]
        blue_mask = cv2.inRange(uv, self.LOWER_BLUE, self.UPPER_BLUE)
        orange_mask = cv2.inRange(uv, self.LOWER_ORANGE, self.UPPER_ORANGE)

        return self._find_blocks([blue_mask, orange_mask], ["blue", "orange"])

    def check_field_bonds(self, frame):
        logger.info("Fetching drivable field boundaries...")

        y = frame[:, :, 0]
        white_mask = cv2.inRange(y, self.LOWER_WHITE, self.UPPER_WHITE)

        zones = self._find_blocks([white_mask], ["white"])
        # Only one zone should be detected, so we can just return the first element of the tuple
        return zones[0] if zones else None

    def find_walls(self, frame):
        logger.info("Checking for walls")

        y = frame[:, :, 0]
        black_mask = cv2.inRange(y, self.LOWER_BLACK, self.UPPER_BLACK)

        return self._find_blocks([black_mask], ["black"])

    def get_distance(self, items: Sequence[VisionObject], frame_width=Config.VisionConfig.DEFAULT_FRAME_WIDTH) -> list[tuple[Literal["left", "right"], float]]:
        center_x = frame_width // 2

        dists: List[Tuple[Literal["left", "right"], float]] = []

        for item in items:  # Should already be sorted
            if item.x_centroid >= center_x and item.y_centroid > Config.VisionConfig.MIN_CENTROID_Y:  # Wall on the right, get left edge
                x, *_ = item.bbox
                dists.append(x - center_x)
            # Wall on the left, get right edge, crop to bottom ROI
            if item.x_centroid < center_x and item.y_centroid > Config.VisionConfig.MIN_CENTROID_Y:
                x, _, w, _ = item.bbox
                # x + w is the right edge of the object, so distance from right edge of frame is frame_width - (x + w)
                dists.append(("right", frame_width - (x + w)))

        return dists

    def get_obstacle_path_x(self, obstacles: Sequence[VisionObject], wall_dists: dict[str, float], obstacle_dists: Sequence[Tuple[Literal["left", "right"], float]]) -> float:
        if not obstacles or not obstacle_dists:
            return 0.0

        obstacle = obstacles[0]
        obstacle_side, obstacle_dist = obstacle_dists[0]
        wall_dist = wall_dists.get(obstacle_side, float("inf"))

        if next(self._obstacle_path_frame_modulo) == 0 or self._obstacle_path_spline is None or self._obstacle_last_y is None:
            if not np.isfinite(obstacle_dist) or not np.isfinite(wall_dist):
                return 0.0

            point_1 = (0.0, 256.0)
            point_2 = (mean([obstacle_dist, wall_dist]),
                       float(obstacle.y_centroid))

            if np.isclose(point_2[0], point_1[0]):
                return 0.0

            self._obstacle_path_spline = CubicSpline(
                [point_2[0], point_1[0]],
                [point_2[1], point_1[1]],
                bc_type=((1, 0), (1, 0)),
            )
            self._obstacle_last_y = float(obstacle.y_centroid)

        delta_y = float(self._obstacle_last_y - obstacle.y_centroid)
        return float(self._obstacle_path_spline(delta_y))

    def get_wall_distance(self, items: Sequence[VisionObject], frame_width=Config.VisionConfig.DEFAULT_FRAME_WIDTH):
        center_x = frame_width // 2

        wall_dists = {
            "left": float("inf"),
            "right": float("inf")
        }

        if not items:
            return wall_dists

        for item in items:
            # Wall on the right, get left edge, crop to bottom ROI
            if item.x_centroid >= center_x and item.y_centroid > Config.VisionConfig.MIN_CENTROID_Y:
                x, *_ = item.bbox
                wall_dists["right"] = x - center_x
            # Wall on the left, get right edge, crop to bottom ROI
            if item.x_centroid < center_x and item.y_centroid > Config.VisionConfig.MIN_CENTROID_Y:
                x, _, w, _ = item.bbox
                wall_dists["left"] = center_x - (x + w)

        return wall_dists

    def comprehensive_analysis(self, frame):
        zone, walls, obstacles, corner_lines = (
            self.check_field_bonds(frame),
            self.find_walls(frame),
            self.find_obstacles(frame),
            self.check_corner_lines(frame),
        )

        wall_dists = self.get_wall_distance(walls)
        obstacle_dists = self.get_distance(obstacles)
        obstacle_path_x = self.get_obstacle_path_x(
            obstacles, wall_dists, obstacle_dists)

        return zone, walls, obstacles, corner_lines, wall_dists, obstacle_dists, obstacle_path_x


class OpenChallengeVisionProcessor(VisionProcessor):
    def __init__(self, *args, **kwargs):
        super(OpenChallengeVisionProcessor, self).__init__(*args, **kwargs)

    # Bogus overwrite to disable perspective transforms on basic version
    def _perspective_transform(self, contours: Sequence[VisionObject], colors: Sequence[str]) -> Sequence[VisionObject]:
       return np.array([VisionObject(contour=contour, color=color) for contour, color in zip(contours, colors)])


class AsyncMultiprocessingVisionProcessor(VisionProcessor):
    def __init__(self, *args, **kwargs):
        super(AsyncMultiprocessingVisionProcessor,
              self).__init__(*args, **kwargs)
        self.executor = None
        self.loop = asyncio.get_event_loop()

    async def __aenter__(self):
        self.executor = ThreadPoolExecutor(6)
        return self

    async def __aexit__(self, *args, **kwargs):  # Error handling in main loop
        if hasattr(self, "executor") and self.executor:
            self.executor.shutdown(wait=False)

    async def find_obstacles(self, frame) -> tuple[VisionObject]:
        return await self.loop.run_in_executor(self.executor, super(AsyncMultiprocessingVisionProcessor, self).find_obstacles, frame)

    async def check_field_bonds(self, frame):
        return await self.loop.run_in_executor(self.executor, super(AsyncMultiprocessingVisionProcessor, self).check_field_bonds, frame)

    async def check_corner_lines(self, frame):
        return await self.loop.run_in_executor(self.executor, super(AsyncMultiprocessingVisionProcessor, self).check_corner_lines, frame)

    async def find_walls(self, frame):
        return await self.loop.run_in_executor(self.executor, super(AsyncMultiprocessingVisionProcessor, self).find_walls, frame)

    async def get_distance(self, items: Sequence[VisionObject], frame_width=Config.VisionConfig.DEFAULT_FRAME_WIDTH):
        return await self.loop.run_in_executor(self.executor, super(AsyncMultiprocessingVisionProcessor, self).get_distance, items, frame_width)

    async def get_wall_distance(self, walls: Sequence[VisionObject], frame_width=Config.VisionConfig.DEFAULT_FRAME_WIDTH):
        return await self.loop.run_in_executor(self.executor, super(AsyncMultiprocessingVisionProcessor, self).get_wall_distance, walls, frame_width)

    async def get_obstacle_path_x(self, obstacles: Sequence[VisionObject], wall_dists: dict[str, float], obstacle_dists: Sequence[Tuple[Literal["left", "right"], float]]):
        return await self.loop.run_in_executor(self.executor, super(AsyncMultiprocessingVisionProcessor, self).get_obstacle_path_x, obstacles, wall_dists, obstacle_dists)

    async def comprehensive_analysis(self, shm: str, receiver: Connection, sender: Connection, ) -> NoReturn:
        shm = shared_memory.SharedMemory(name=shm)
        frame_width = Config.VisionConfig.ANALYSIS_FRAME_WIDTH
        frame_height = Config.VisionConfig.ANALYSIS_FRAME_HEIGHT
        frame_channels = Config.VisionConfig.ANALYSIS_FRAME_CHANNELS
        frame_size = frame_width * frame_height * frame_channels

        async for _ in AsyncMultiprocessingVisionProcessor.async_pipe_reader(receiver):
            frame = np.ndarray((frame_height, frame_width, frame_channels),
                               dtype=np.uint8, buffer=shm.buf[:frame_size])
            round1 = [
                self.check_field_bonds(frame),
                self.find_walls(frame),
                self.find_obstacles(frame),
                self.check_corner_lines(frame)
            ]
            zone, walls, obstacles, corner_lines = await asyncio.gather(*round1)
            round2 = [
                self.get_wall_distance(walls),
                self.get_distance(obstacles)
            ]
            wall_dists, obstacle_dists = await asyncio.gather(*round2)
            obstacle_path_x = await self.get_obstacle_path_x(obstacles, wall_dists, obstacle_dists)

            sender.send((zone, walls, obstacles, corner_lines,
                        wall_dists, obstacle_dists, obstacle_path_x,))

    @staticmethod
    async def async_pipe_reader(receiver: Connection):
        loop = asyncio.get_event_loop()
        data_event = asyncio.Event()

        def yielder(): return data_event.set()
        loop.add_reader(receiver.fileno(), yielder)

        while True:
            await data_event.wait()

            while receiver.poll():
                yield receiver.recv()

            data_event.clear()

    @staticmethod
    def get_perspective_transform():
        src = np.array([
            [0, 0],
            [0, 0],
            [0, 0],
            [0, 0],
        ], dtype=np.float32)
        dst = np.array([
            [0, 0],
            [0, 0],
            [0, 0],
            [0, 0],
        ], dtype=np.float32)

        return cv2.getPerspectiveTransform(src, dst)


# This feel like java "FeatureAbstractFactoryProviderFactory" xd
class OpenChallengeAsyncMultiprocessingVisionProcessor(AsyncMultiprocessingVisionProcessor):
    def __init__(self, *args, **kwargs):
        super(OpenChallengeAsyncMultiprocessingVisionProcessor,
              self).__init__(*args, **kwargs)

    def _perspective_transform(self, contours: np.ndarray, colors: Sequence[str]) -> np.ndarray[VisionObject]:
        return np.array([VisionObject(contour=contour, color=color) for contour, color in zip(contours, colors)])

    async def comprehensive_analysis(self, shm: str, receiver: Connection[Any, Any], sender: Connection[Any, Any]) -> NoReturn:
        shm = shared_memory.SharedMemory(name=shm)
        frame_width = Config.VisionConfig.ANALYSIS_FRAME_WIDTH
        frame_height = Config.VisionConfig.ANALYSIS_FRAME_HEIGHT
        frame_channels = Config.VisionConfig.ANALYSIS_FRAME_CHANNELS
        frame_size = frame_width * frame_height * frame_channels

        async for _ in AsyncMultiprocessingVisionProcessor.async_pipe_reader(receiver):
            frame = np.ndarray((frame_height, frame_width, frame_channels),
                               dtype=np.uint8, buffer=shm.buf[:frame_size])
            round1 = [
                self.check_field_bonds(frame),
                self.find_walls(frame),
                self.check_corner_lines(frame)
            ]
            zone, walls, corner_lines = await asyncio.gather(*round1)
            round2 = [
                self.get_wall_distance(walls),
            ]
            wall_dists = await asyncio.gather(*round2)

            # Removed obstacle data for open challenge
            sender.send((zone, walls, corner_lines, wall_dists))
