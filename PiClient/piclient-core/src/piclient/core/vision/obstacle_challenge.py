"""Obstacle Challenge vision processor.

Extends :class:`VisionProcessor`
"""

from typing import Any

import cv2
import numpy as np
from scipy.spatial.distance import cdist

from loguru import logger
from ..lib import GLOBAL_CONFIG, export
from .base import VisionProcessor
from .data import VisionObject, WallsAndObstacles, ObstacleChallengeWalls


@export
class ObstacleChallengeVisionProcessor(VisionProcessor):
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
    _DEFAULT_PERSPECTIVE_TRANSFORM: np.ndarray[tuple[int, ...], np.dtype[np.float32 | np.float64]] = GLOBAL_CONFIG(
    ).VisionConfig.PERSPECTIVE_TRANSFORM
    _DEFAULT_FRAME_HEIGHT: int = GLOBAL_CONFIG().CameraConfig.OUTPUT_HEIGHT
    _DEFAULT_FRAME_WIDTH: int = GLOBAL_CONFIG().CameraConfig.OUTPUT_WIDTH

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
        frame_width: int | None = None,
        frame_height: int | None = None,
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

    def get_midpoint_to_wall(self, obstacle: VisionObject, walls: ObstacleChallengeWalls) -> tuple[int, int]:
        """
        Calculates the exact midpoint of the shortest line connecting an obstacle contour to the corresponding wall contour.
        Quickly finds the closest points on the wall segments to the obstacle's vertices and computes the geometric midpoint.
        Use this method to get the most accurate midpoint for navigation or obstacle avoidance.

        Returns:
            (x, y) tuple of the geometric midpoint
        """

        if walls.left_raw is None or walls.right_raw is None:
            raise ValueError(
                "Wall contours must be provided for midpoint calculation.")

        # v1: vertices of contour 1, p1_a: start points of edges of contour 1, p2_a: end points of edges of contour 1
        v1, p1_a, p2_a = self.get_segments_and_vertices(obstacle.contour)
        # v2: vertices of contour 2, p1_b: start points of edges of contour 2, p2_b: end points of edges of contour 2
        v2, p1_b, p2_b = self.get_segments_and_vertices(
            walls.left_raw.contour if obstacle.color == "green" else walls.right_raw.contour)

        # Figure out where to aim from each vertex of contour 1 to the each edge of contour 2, and vice versa
        candidates_on_b = self._project_points_to_segments(
            # Shape: (N, M, 2) - How to get from each vertex of contour 1 to each edge of contour 2
            v1, p1_b, p2_b)
        candidates_on_a = self._project_points_to_segments(
            # Shape: (M, N, 2) - How to get from each vertex of contour 2 to each edge of contour 1
            v2, p1_a, p2_a)

        # Flatten candidates to simple 2D arrays of points
        # Where to aim to hit contour 2 from contour 1's vertices
        flat_candidates_b = candidates_on_b.reshape(-1, 2)
        # Where to aim to hit contour 1 from contour 2's vertices
        flat_candidates_a = candidates_on_a.reshape(-1, 2)

        # Now compute the actual distances between the vertices of contour 1 and the closest points on contour 2's edges, and vice versa
        # Okay, now I know where to aim, let me see how far I have to go to get there
        dist_matrix_1_to_2 = cdist(v1, flat_candidates_b)
        idx_1_to_2 = np.unravel_index(
            # Flatten the distance matrix to find the index of the minimum distance, then unravel it back to 2D indices
            np.argmin(dist_matrix_1_to_2), dist_matrix_1_to_2.shape)
        # get the actual minimum distance value
        min_dist_1 = dist_matrix_1_to_2[idx_1_to_2]

        # Same process for vertices of 2 against edges of 1
        dist_matrix_2_to_1 = cdist(v2, flat_candidates_a)
        idx_2_to_1 = np.unravel_index(
            np.argmin(dist_matrix_2_to_1), dist_matrix_2_to_1.shape)
        min_dist_2 = dist_matrix_2_to_1[idx_2_to_1]

        if min_dist_1 < min_dist_2:  # Which is samller
            # the starting vertex of contour 1 that is closest to contour 2
            pt1 = v1[idx_1_to_2[0]]
            # the closest point on contour 2's edge to that vertex
            pt2 = flat_candidates_b[idx_1_to_2[1]]
        else:
            # the closest point on contour 1's edge to that vertex
            pt1 = flat_candidates_a[idx_2_to_1[1]]
            # the starting vertex of contour 2 that is closest to contour 1
            pt2 = v2[idx_2_to_1[0]]

        # midpoint calculation is straightforward
        midpoint_x = int((pt1[0] + pt2[0]) / 2)
        midpoint_y = int((pt1[1] + pt2[1]) / 2)

        return (midpoint_x, midpoint_y)

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

        center_area = frame[self.center_wall_roi]
        obstacle_area = frame[self.obstacle_roi]

        wall_masked = cv2.inRange(
            frame, self.lower_black, self.upper_black)

        walls = self._find_blocks([wall_masked], ["walls"])

        center_masked = cv2.inRange(
            center_area, self.lower_black, self.upper_black)
        obstacle_masked_red = cv2.inRange(
            obstacle_area, self.lower_red_obstacle, self.upper_red_obstacle)
        obstacle_masked_green = cv2.inRange(
            obstacle_area, self.lower_green_obstacle, self.upper_green_obstacle)

        center_pixels = cv2.countNonZero(center_masked)
        obstacles = self._find_blocks(
            [obstacle_masked_red, obstacle_masked_green], ["red", "green"])
        if len(obstacles) == 0:
            obstacles = None


        left_wall = None
        right_wall = None
        left_dist = float('inf')
        right_dist = float('inf')

        # Walls is already sorted by size, the biggest walls are first.
        for wall in walls:
            if wall.x_centroid < self.frame_width / 2:
                left_wall = wall
                left_dist = self.horizontal_distance(wall, self.frame_width / 2)
                break

        for wall in walls:
            if wall.x_centroid >= self.frame_width / 2:
                right_wall = wall
                right_dist = self.horizontal_distance(wall, self.frame_width / 2)
                break

        if not left_wall or not right_wall:
            logger.debug(
                "Could not find both walls, left_dist and right_dist set to infinity.")

            return WallsAndObstacles(
                walls=ObstacleChallengeWalls(
                    left=left_dist,
                    left_raw=None,
                    right=right_dist,
                    right_raw=None,
                    center=center_pixels,
                    max_distance=self.frame_width // 2,
                    center_area=center_area.size // center_area.shape[2]  # Adjust for number of channels
                ),
                obstacles=obstacles
            )

        walls_and_obstacles = WallsAndObstacles(
            walls=ObstacleChallengeWalls(
                left=left_dist,
                left_raw=left_wall if len(walls) >= 2 else None,
                right=right_dist,
                right_raw=right_wall if len(walls) >= 2 else None,
                center=center_pixels,
                max_distance=self.frame_width // 2,
                center_area=center_area.size // center_area.shape[2]
            ),
            obstacles=obstacles
        )

        logger.debug(f"Walls and Obstacles: {walls_and_obstacles}")
        return walls_and_obstacles

    def get_target(self, walls_and_obstacles: WallsAndObstacles) -> tuple[int, int] | None:
        """Compute target point based on wall and obstacle information.

        :param walls_and_obstacles: Walls and obstacles data.
        :returns: Target point as (x, y) tuple or None if no target.
        :rtype: tuple[int, int] | None
        """
        target_point: tuple[int, int] | None = None

        if (walls_and_obstacles.obstacles is None
            or len(walls_and_obstacles.obstacles) == 0
            or walls_and_obstacles.walls.left_raw is None
                or walls_and_obstacles.walls.right_raw is None):
            return target_point

        largest_obstacle = walls_and_obstacles.obstacles[0]
        if largest_obstacle and largest_obstacle.contour.size > 0:
            target_point = self.get_midpoint_to_wall(
                largest_obstacle, walls_and_obstacles.walls)

        return target_point
