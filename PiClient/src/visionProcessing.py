from multiprocessing.connection import Connection
import cv2
import numpy as np
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import NoReturn, Sequence, Tuple
from loguru import logger
from multiprocessing import shared_memory
from dataclasses import dataclass
from src.config import Config

@dataclass
class VisionObject():
    contour: np.ndarray
    color: str
    
    def __post_init__(self):
        self.bbox: tuple[float, float, float, float] = cv2.boundingRect(self.contour)
        x, y, w, h = self.bbox
        self.x_centroid: float = x + w/2
        self.y_centroid: float = y + h/2
        # Bottom y deprecated because perspective transform makes everything top-down
        
class VisionProcessor(): 
    PERSPECTIVE_TRANSFORM = np.array((Config.VisionConfig.PERSPECTIVE_TRANSFORM), dtype=np.float32)

    def __init__(self):
        # I will add autotuning soonTM lol so yes these are instance variables, not class variables
        self.LOWER_ORANGE = np.array(Config.VisionConfig.LOWER_ORANGE)
        self.UPPER_ORANGE = np.array(Config.VisionConfig.UPPER_ORANGE)

        self.LOWER_BLUE = np.array(Config.VisionConfig.LOWER_BLUE)
        self.UPPER_BLUE = np.array(Config.VisionConfig.UPPER_BLUE)

        self.LOWER_GREEN = np.array(Config.VisionConfig.LOWER_GREEN)
        self.UPPER_GREEN = np.array(Config.VisionConfig.UPPER_GREEN)

        self.LOWER_RED = np.array(Config.VisionConfig.LOWER_RED)
        self.UPPER_RED = np.array(Config.VisionConfig.UPPER_RED)

        self.LOWER_BLACK = Config.VisionConfig.LOWER_BLACK
        self.UPPER_BLACK = Config.VisionConfig.UPPER_BLACK
        self.LOWER_WHITE = Config.VisionConfig.LOWER_WHITE
        self.UPPER_WHITE = Config.VisionConfig.UPPER_WHITE

    def _perspective_transform(self, contours: np.ndarray, colors: Sequence[str]) -> np.ndarray[VisionObject]: # Applying cv2.perspectiveTransform is much more efficient than warping whole frame
        contours = np.array([VisionObject(contour=cv2.perspectiveTransform(contour, self.PERSPECTIVE_TRANSFORM), color=color) for contour, color in zip(contours, colors)])
        return contours

    def _find_blocks(self, masks, colors):
        contours = []
        detected_colors = []

        for mask, color in zip(masks, colors):
            detected_contours, *_ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
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
        return zones[0] if zones else None # Only one zone should be detected, so we can just return the first element of the tuple
    
    def find_walls(self, frame):
        logger.info("Checking for walls")

        y = frame[:, :, 0]
        black_mask = cv2.inRange(y, self.LOWER_BLACK, self.UPPER_BLACK)

        return self._find_blocks([black_mask], ["black"])
    
    def get_distance(self, items: Sequence[VisionObject], frame_width=Config.VisionConfig.DEFAULT_FRAME_WIDTH):
        center_x = frame_width // 2

        dists = []

        if not items:
            return len(items) * [float("inf")]
        
        for item in items: # Should already be sorted
            if item.x_centroid >= center_x and item.y_centroid > Config.VisionConfig.MIN_CENTROID_Y: # Wall on the right, get left edge, crop to bottom ROI
                x, *_ = item.bbox
                dists.append(x - center_x)
            if item.x_centroid < center_x and item.y_centroid > Config.VisionConfig.MIN_CENTROID_Y: # Wall on the left, get right edge, crop to bottom ROI
                x, _, w, _ = item.bbox
                dists.append(center_x - (x + w))

        return dists

    def get_wall_distance(self, items: Sequence[VisionObject], frame_width=Config.VisionConfig.DEFAULT_FRAME_WIDTH):
        center_x = frame_width // 2

        wall_dists = {
            "left": float("inf"),
            "right": float("inf")
        }

        if not items:
            return wall_dists

        for item in items:
            if item.x_centroid >= center_x and item.y_centroid > Config.VisionConfig.MIN_CENTROID_Y: # Wall on the right, get left edge, crop to bottom ROI
                x, *_ = item.bbox
                wall_dists["right"] = x - center_x
            if item.x_centroid < center_x and item.y_centroid > Config.VisionConfig.MIN_CENTROID_Y: # Wall on the left, get right edge, crop to bottom ROI
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

        return zone, walls, obstacles, corner_lines, wall_dists, obstacle_dists
    
class AsyncMultiprocessingVisionProcessor(VisionProcessor):
    def __init__(self, *args):
        super(AsyncMultiprocessingVisionProcessor, self).__init__(*args)
        self.executor = None
        self.loop = asyncio.get_event_loop()

    async def __aenter__(self):
        self.executor = ThreadPoolExecutor(6)
        return self

    async def __aexit__(self, *args): # Error handling in main loop
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
    
    async def comprehensive_analysis(self, shm: str, receiver: Connection, sender: Connection, ) -> NoReturn:
        shm = shared_memory.SharedMemory(name=shm)
        frame_width = Config.VisionConfig.ANALYSIS_FRAME_WIDTH
        frame_height = Config.VisionConfig.ANALYSIS_FRAME_HEIGHT
        frame_channels = Config.VisionConfig.ANALYSIS_FRAME_CHANNELS
        frame_size = frame_width * frame_height * frame_channels

        async for _ in AsyncMultiprocessingVisionProcessor.async_pipe_reader(receiver):
            frame = np.ndarray((frame_height, frame_width, frame_channels), dtype=np.uint8, buffer=shm.buf[:frame_size])
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

            sender.send((zone, walls, obstacles, corner_lines, wall_dists, obstacle_dists,))

    @staticmethod
    async def async_pipe_reader(receiver: Connection):
        loop = asyncio.get_event_loop()
        data_event = asyncio.Event()

        yielder = lambda: data_event.set()
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