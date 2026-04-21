import cv2
import numpy as np
from math import isinf
from typing import Sequence
from src_min import logger
from dataclasses import dataclass
from .config import Config


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
        Config.VisionConfig.PERSPECTIVE_TRANSFORM, dtype=np.float32)

    def __init__(self):
        # I will add autotuning soonTM lol so yes these are instance variables, not class variables
        self.lower_orange = np.array(Config.VisionConfig.LOWER_ORANGE)
        self.upper_orange = np.array(Config.VisionConfig.UPPER_ORANGE)

        self.lower_blue = np.array(Config.VisionConfig.LOWER_BLUE)
        self.upper_blue = np.array(Config.VisionConfig.UPPER_BLUE)

        self.lower_green = np.array(Config.VisionConfig.LOWER_GREEN)
        self.upper_green = np.array(Config.VisionConfig.UPPER_GREEN)

        self.lower_red = np.array(Config.VisionConfig.LOWER_RED)
        self.upper_red = np.array(Config.VisionConfig.UPPER_RED)

    # Applying cv2.perspectiveTransform is much more efficient than warping whole frame
    def _perspective_transform(self, contours: np.ndarray, colors: Sequence[str]) -> np.ndarray:
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
        green_mask = cv2.inRange(uv, self.lower_green, self.upper_green)
        red_mask = cv2.inRange(uv, self.lower_red, self.upper_red)

        return self._find_blocks([green_mask, red_mask], ["green", "red"])

    def check_corner_lines(self, frame):
        logger.info("Searching for turn aids...")
        uv = frame[:, :, 1:3]
        blue_mask = cv2.inRange(uv, self.lower_blue, self.upper_blue)
        orange_mask = cv2.inRange(uv, self.lower_orange, self.upper_orange)

        return self._find_blocks([blue_mask, orange_mask], ["blue", "orange"])

    def check_field_bounds(self, frame):
        logger.info("Fetching drivable field boundaries...")

        y = frame[:, :, 0]
        white_mask = cv2.inRange(
            y, Config.VisionConfig.LOWER_WHITE, Config.VisionConfig.UPPER_WHITE)

        zones = self._find_blocks([white_mask], ["white"])
        # Only one zone should be detected, so we can just return the first element of the tuple
        return zones[0] if zones else None

    def check_field_bonds(self, frame):
        # Compatibility alias for older call sites.
        return self.check_field_bounds(frame)

    def find_walls(self, frame):
        logger.info("Checking for walls")

        y = frame[:, :, 0]
        black_mask = cv2.inRange(
            y, Config.VisionConfig.LOWER_BLACK, Config.VisionConfig.UPPER_BLACK)

        return self._find_blocks([black_mask], ["black"])

    def get_distance(self, items: Sequence[VisionObject], frame_width=Config.VisionConfig.DEFAULT_FRAME_WIDTH):
        center_x = frame_width // 2

        dists = []

        if not items:
            return len(items) * [float("inf")]

        for item in items:  # Should already be sorted
            # Wall on the right, get left edge, crop to bottom ROI
            if item.x_centroid >= center_x and item.y_centroid > Config.VisionConfig.MIN_CENTROID_Y:
                x, *_ = item.bbox
                dists.append(x - center_x)
            # Wall on the left, get right edge, crop to bottom ROI
            if item.x_centroid < center_x and item.y_centroid > Config.VisionConfig.MIN_CENTROID_Y:
                x, _, w, _ = item.bbox
                dists.append(center_x - (x + w))

        return dists

    def get_obstacle_path_x(self, obstacles: Sequence[VisionObject], wall_dists: dict[str, float], frame_width=Config.VisionConfig.DEFAULT_FRAME_WIDTH) -> float:
        if not obstacles:
            return 0.0

        center_x = frame_width // 2
        obstacle = obstacles[0]
        obstacle_offset = float(obstacle.x_centroid - center_x)

        # Prefer steering around obstacle toward side with more observed clearance.
        left_clearance = wall_dists.get("left", float("inf"))
        right_clearance = wall_dists.get("right", float("inf"))
        if not isinf(left_clearance) and not isinf(right_clearance):
            if left_clearance > right_clearance:
                return -abs(obstacle_offset)
            return abs(obstacle_offset)

        return obstacle_offset

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
            self.check_field_bounds(frame),
            self.find_walls(frame),
            self.find_obstacles(frame),
            self.check_corner_lines(frame),
        )

        wall_dists = self.get_wall_distance(walls)
        obstacle_dists = self.get_distance(obstacles)
        obstacle_path_x = self.get_obstacle_path_x(obstacles, wall_dists)

        return zone, walls, obstacles, corner_lines, wall_dists, obstacle_dists, obstacle_path_x

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
