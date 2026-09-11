"""Obstacle Challenge vision processor.

Extends :class:`VisionProcessor`
"""

from typing import Any

import cv2
import numpy as np

from ..lib import GLOBAL_CONFIG, export
from .open_challenge import OpenChallengeVisionProcessor
from .data import VisionObject, WallsAndObstacles, Walls, ParkingLot


@export
class ObstacleChallengeVisionProcessor(OpenChallengeVisionProcessor):
    """Vision processor specialised for the Obstacle Challenge.

    Measures normalised black-pixel density in left and right ROIs
    to estimate wall distances.

    :ivar left_wall_roi: Region-of-interest slice for the left wall.
    :ivar right_wall_roi: Region-of-interest slice for the right wall.
    """

    _DEFAULT_CENTER_WALL_ROI = GLOBAL_CONFIG().VisionConfig.CENTER_WALL_ROI

    _DEFAULT_OBSTACLE_ROI: tuple[slice, slice] = GLOBAL_CONFIG(
    ).VisionConfig.OBSTACLE_ROI
    _DEFAULT_LOWER_RED_OBSTACLE: np.ndarray[tuple[int, ...], np.dtype[np.uint8]] = GLOBAL_CONFIG(
    ).VisionConfig.LOWER_RED_OBSTACLE
    _DEFAULT_UPPER_RED_OBSTACLE: np.ndarray[tuple[int, ...], np.dtype[np.uint8]] = GLOBAL_CONFIG(
    ).VisionConfig.UPPER_RED_OBSTACLE
    _DEFAULT_LOWER_GREEN_OBSTACLE: np.ndarray[tuple[int, ...], np.dtype[np.uint8]] = GLOBAL_CONFIG(
    ).VisionConfig.LOWER_GREEN_OBSTACLE
    _DEFAULT_UPPER_GREEN_OBSTACLE: np.ndarray[tuple[int, ...], np.dtype[np.uint8]] = GLOBAL_CONFIG(
    ).VisionConfig.UPPER_GREEN_OBSTACLE
    _DEFAULT_LOWER_PARKING_LOT: np.ndarray[tuple[int, ...], np.dtype[np.uint8]] = GLOBAL_CONFIG(
    ).VisionConfig.LOWER_PARKING_LOT
    _DEFAULT_UPPER_PARKING_LOT: np.ndarray[tuple[int, ...], np.dtype[np.uint8]] = GLOBAL_CONFIG(
    ).VisionConfig.UPPER_PARKING_LOT
    _DEFAULT_PERSPECTIVE_TRANSFORM: np.ndarray[tuple[int, ...], np.dtype[np.float32 | np.float64]] = GLOBAL_CONFIG(
    ).VisionConfig.PERSPECTIVE_TRANSFORM
    _DEFAULT_FRAME_HEIGHT: int = GLOBAL_CONFIG().CameraConfig.OUTPUT_HEIGHT
    _DEFAULT_FRAME_WIDTH: int = GLOBAL_CONFIG().CameraConfig.OUTPUT_WIDTH

    _DEFAULT_OBSTACLE_BASE_OFFSET: float = GLOBAL_CONFIG().ObstacleChallengeConfig.OBSTACLE_BASE_OFFSET
    _DEFAULT_OBSTACLE_OFFSET_SCALING_FACTOR: float = GLOBAL_CONFIG().ObstacleChallengeConfig.OBSTACLE_OFFSET_SCALING_FACTOR

    def __init__(
        self,
        center_wall_roi: tuple[slice, slice] | None = None,
        obstacle_roi: tuple[slice, slice] | None = None,
        upper_red_obstacle: np.ndarray[tuple[int, ...],
                                       np.dtype[np.uint8]] | None = None,
        lower_red_obstacle: np.ndarray[tuple[int, ...],
                                       np.dtype[np.uint8]] | None = None,
        upper_green_obstacle: np.ndarray[tuple[int, ...],
                                         np.dtype[np.uint8]] | None = None,
        lower_green_obstacle: np.ndarray[tuple[int, ...],
                                         np.dtype[np.uint8]] | None = None,
        lower_parking_lot: np.ndarray[tuple[int, ...],
                          np.dtype[np.uint8]] | None = None,
        upper_parking_lot: np.ndarray[tuple[int, ...],
                          np.dtype[np.uint8]] | None = None,
        frame_width: int | None = None,
        frame_height: int | None = None,
        obstacle_base_offset: float | None = None,
        obstacle_offset_scaling_factor: float | None = None,
        obstacle_tracking_radius: float | None = None,
        obstacle_invalidation_roi: tuple[float, float, float] | None = None,
        *args: Any,
        **kwargs: Any
    ):
        """Initialise the Obstacle Challenge vision processor.

        Forwards most arguments to :class:`VisionProcessor`.  Accepts
        optional keyword-only overrides for the wall ROIs.

        :param left_wall_roi: NumPy slice for the left wall (default from Config).
        :param right_wall_roi: NumPy slice for the right wall (default from Config).
        :param center_wall_roi: NumPy slice for the center wall (default from Config).
        :param obstacle_roi: NumPy slice for the obstacle region (default from Config).
        :param upper_red_obstacle: Upper HSV bound for red obstacle detection (default from Config).
        :param lower_red_obstacle: Lower HSV bound for red obstacle detection (default from Config).
        :param upper_green_obstacle: Upper HSV bound for green obstacle detection (default from Config).
        :param lower_green_obstacle: Lower HSV bound for green obstacle detection (default from Config).
        """
        super(ObstacleChallengeVisionProcessor, self).__init__(*args, **kwargs)
        self.center_wall_roi = (
            center_wall_roi
            if center_wall_roi is not None
            else self._DEFAULT_CENTER_WALL_ROI
        )
        self.obstacle_roi = (
            obstacle_roi
            if obstacle_roi is not None
            else self._DEFAULT_OBSTACLE_ROI
        )
        self.upper_red_obstacle = (
            upper_red_obstacle
            if upper_red_obstacle is not None
            else self._DEFAULT_UPPER_RED_OBSTACLE
        )
        self.lower_red_obstacle = (
            lower_red_obstacle
            if lower_red_obstacle is not None
            else self._DEFAULT_LOWER_RED_OBSTACLE
        )
        self.upper_green_obstacle = (
            upper_green_obstacle
            if upper_green_obstacle is not None
            else self._DEFAULT_UPPER_GREEN_OBSTACLE
        )
        self.lower_green_obstacle = (
            lower_green_obstacle
            if lower_green_obstacle is not None
            else self._DEFAULT_LOWER_GREEN_OBSTACLE
        )
        self.lower_parking_lot = (
            lower_parking_lot
            if lower_parking_lot is not None
            else self._DEFAULT_LOWER_PARKING_LOT
        )
        self.upper_parking_lot = (
            upper_parking_lot
            if upper_parking_lot is not None
            else self._DEFAULT_UPPER_PARKING_LOT
        )
        self.frame_width = (
            frame_width
            if frame_width is not None
            else self._DEFAULT_FRAME_WIDTH
        )
        self.frame_height = (
            frame_height
            if frame_height is not None
            else self._DEFAULT_FRAME_HEIGHT
        )
        self.obstacle_base_offset = (
            obstacle_base_offset
            if obstacle_base_offset is not None
            else self._DEFAULT_OBSTACLE_BASE_OFFSET
        )
        self.obstacle_offset_scaling_factor = (
            obstacle_offset_scaling_factor
            if obstacle_offset_scaling_factor is not None
            else self._DEFAULT_OBSTACLE_OFFSET_SCALING_FACTOR
        )
        self.max_distance = float(np.hypot(self.frame_width / 2, self.frame_height))
        self._tracked_obstacle: VisionObject | None = None
        self._invalidated_obstacle: VisionObject | None = None

    @staticmethod
    def get_segments_and_vertices(contour: np.ndarray[tuple[int, int], np.dtype[np.int32]]) -> tuple[
        np.ndarray[tuple[int, int], np.dtype[np.int32]],
        np.ndarray[tuple[int, int], np.dtype[np.int32]],
        np.ndarray[tuple[int, int], np.dtype[np.int32]]
    ]:
        """Extract contour vertices and edge segments."""
        vertices = contour.reshape(-1, 2)

        # Create segment starts and ends for each edge of the polygon
        p1 = vertices
        # shift by one to get the next vertex as the end of the segment
        p2 = np.roll(vertices, -1, axis=0)
        return vertices, p1, p2

    @staticmethod
    def _project_points_to_segments(
            pts: np.ndarray[tuple[int, int], np.dtype[np.int32]],
        seg_p1: np.ndarray[tuple[int, int], np.dtype[np.int32]],
        seg_p2: np.ndarray[tuple[int, int], np.dtype[np.int32]]
    ) -> np.ndarray[tuple[int, int], np.dtype[np.float64]]:
        """Finds the closest points on segments using vector projection."""
        seg_vec = seg_p2 - seg_p1
        seg_len_sq = np.sum(seg_vec**2, axis=1)
        seg_len_sq[seg_len_sq == 0] = 1e-6  # Prevent division by zero

        # Broadcast to compare all vertices against all segments
        # Cartesian product of points and the first point in each segment
        grid_pts, grid_seg = np.meshgrid(
            np.arange(len(pts)), np.arange(len(seg_p1)), indexing='ij')
        # Vector from segment start to point
        p_vec = pts[grid_pts] - seg_p1[grid_seg]

        # Dot product to find projection scalar (Where should I aim along the segment vector to get closest point)
        t = np.sum(p_vec * seg_vec[None, :, :], axis=2) / seg_len_sq[None, :]
        # Don't aim outside the segment, clamp to [0, 1]
        t = np.clip(t, 0.0, 1.0)

        # Denormalize the projection scalar to get the closest point on the segment
        closest_pts = seg_p1[None, :, :] + t[:, :, None] * seg_vec[None, :, :]
        return closest_pts  # Where do I aim to hit the segment closest to my point?

    @staticmethod
    def horizontal_distance(object_: VisionObject, x: float) -> float:
        """Calculates the unsigned distance between the centroid and a vertical line at x."""
        return abs(object_.x_centroid - x)


    def get_walls_and_obstacles(self, frame: np.ndarray):
        """Compute normalised wall distances and obstacle information from a preprocessed frame.

        Applies colour thresholding to the left and right ROIs and counts
        non-zero (black) pixels, returning a :class:`Walls` instance.

        :param frame: Preprocessed HSV frame.
        :returns: Normalised wall distances.
        :rtype: WallsAndObstacles
        """
        walls: Walls = self.get_normalized_relative_wall_distances(frame)

        obstacle_area = frame[self.obstacle_roi]

        obstacle_masked_red = cv2.inRange(
            obstacle_area, self.lower_red_obstacle, self.upper_red_obstacle)
        obstacle_masked_green = cv2.inRange(
            obstacle_area, self.lower_green_obstacle, self.upper_green_obstacle)
        parking_masked = cv2.inRange(
            frame, self.lower_parking_lot, self.upper_parking_lot)

        obstacles = self._find_blocks(
            [obstacle_masked_red, obstacle_masked_green], ["red", "green"], min_area=200, max_results=3)
        if len(obstacles) == 0:
            obstacles = None
        parking_lot = list(self._find_blocks([parking_masked], ["parking_lot"], min_area=150, max_results=2))
        parking_lot.sort(key=lambda marker: marker.y_centroid, reverse=True)  # Y increases downwards (bigger = closer)

        return WallsAndObstacles(
            walls=walls,
            obstacles=obstacles,
            parking_lot=ParkingLot(
                closer=parking_lot[0] if parking_lot else None,
                further=parking_lot[1] if len(parking_lot) > 1 else None,
                max_x=self.frame_width,
                max_y=self.frame_height
            )
        )

    def _get_target_point(self, obstacle: VisionObject) -> tuple[float, float]:
        """
        Compute a target point that is offset from the obstacle's centroid.

        Returns:
            (x, y) tuple of the geometric midpoint
        """
        dynamic_offset = obstacle.bbox[2] * self.obstacle_offset_scaling_factor + self.obstacle_base_offset

        target_x = obstacle.x_centroid + dynamic_offset if obstacle.color == "red" else obstacle.x_centroid - dynamic_offset # Green left, red right
        target_y = (obstacle.y_centroid) / 2

        return target_x, target_y

    def get_target(self, walls_and_obstacles: WallsAndObstacles) -> tuple[float, float] | None:
        """Compute target point based on wall and obstacle information.

        Keeps track of the largest obstacle across frames and ignores a stale
        invalidated obstacle until it moves significantly away from the last
        observed invalidation point.

        :param walls_and_obstacles: Walls and obstacles data.
        :returns: Target point as (x, y) tuple or None if no target.
        :rtype: tuple[float, float] | None
        """

        if walls_and_obstacles.obstacles is None:
            return None

        largest_obstacle = walls_and_obstacles.obstacles[0]

        if largest_obstacle and largest_obstacle.contour.size > 0:
            return self._get_target_point(largest_obstacle)

        return None
