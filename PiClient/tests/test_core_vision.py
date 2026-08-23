"""Unit tests for :mod:`piclient.core.vision`.

Covers the vision data structures, the base :class:`VisionProcessor`
preprocessing/contour helpers, and the Open/Obstacle challenge processors.
Deterministic synthetic frames are used instead of real camera data.
"""

import unittest

import numpy as np

from piclient.core.vision import (
    ObstacleChallengeVisionProcessor,
    ObstacleChallengeWalls,
    OpenChallengeVisionProcessor,
    OpenChallengeWalls,
    VisionObject,
    VisionProcessor,
    WallsAndObstacles,
    ParkingLot,
)


def _square_contour(x0: int, y0: int, size: int):
    """Return an OpenCV-style contour (Nx1x2) for an axis-aligned square."""
    return np.array(
        [[[x0, y0]], [[x0 + size, y0]], [[x0 + size, y0 + size]], [[x0, y0 + size]]],
        dtype=np.int32,
    )


class TestVisionObject(unittest.TestCase):
    def test_bbox(self):
        obj = VisionObject(contour=_square_contour(10, 20, 30), color="red")
        x, y, _, _ = obj.bbox
        self.assertEqual((x, y), (10, 20))
        self.assertEqual(obj.color, "red")

    def test_centroid(self):
        obj = VisionObject(contour=_square_contour(0, 0, 10), color="green")
        self.assertAlmostEqual(obj.x_centroid, 5)
        self.assertAlmostEqual(obj.y_centroid, 5)


class TestWallsDataStructures(unittest.TestCase):
    def test_open_challenge_walls_normalisation(self):
        walls = OpenChallengeWalls(
            left=50, right=25, center=10, area=100, center_area=20)
        self.assertAlmostEqual(walls.left, 0.5)
        self.assertAlmostEqual(walls.right, 0.25)
        self.assertAlmostEqual(walls.center, 0.5)

    def test_obstacle_challenge_walls_normalisation(self):
        walls = ObstacleChallengeWalls(
            left=128,
            right=64,
            center=10,
            max_distance=256,
            center_area=20,
            left_raw=None,
            right_raw=None,
        )
        self.assertAlmostEqual(walls.left, 0.5)
        self.assertAlmostEqual(walls.right, 0.25)
        self.assertAlmostEqual(walls.center, 0.5)

    def test_walls_and_obstacles_container(self):
        walls = ObstacleChallengeWalls(
            left=0, right=0, center=0, max_distance=1, center_area=1,
            left_raw=None, right_raw=None,
        )
        container = WallsAndObstacles(walls=walls, obstacles=None, parking_lot=ParkingLot(closer=None, further=None, max_x=1, max_y=1))
        self.assertIs(container.walls, walls)
        self.assertIsNone(container.obstacles)


class TestVisionProcessorBase(unittest.TestCase):
    def setUp(self):
        self.processor = VisionProcessor()

    def test_preprocess_applies_roi_and_hsv(self):
        frame = np.zeros((208, 512, 3), dtype=np.uint8)
        processed = self.processor._preprocess(frame) # pyright: ignore[reportPrivateUsage]
        # INITIAL_ROI crops is applied before hitting the vision processor,
        # so the output shape is the same as the camera
        # output shape.
        self.assertEqual(processed.shape, (208, 512, 3))
        self.assertEqual(processed.dtype, np.uint8)

    def test_simplify_contour_reduces_vertices(self):
        # A noisy near-square should simplify to ~4 corners.
        contour = np.array(
            [[[0, 0]], [[5, 1]], [[10, 0]], [[10, 5]], [
                [10, 10]], [[5, 9]], [[0, 10]], [[0, 5]]],
            dtype=np.int32,
        )
        simplified = VisionProcessor.simplify_contour(contour)
        self.assertLessEqual(simplified.shape[0], contour.shape[0])
        self.assertEqual(simplified.shape[1], 2)

    def test_get_perspective_transform(self):
        src = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=np.float32)
        dst = np.array([[0, 0], [20, 0], [20, 20], [0, 20]], dtype=np.float32)
        matrix = VisionProcessor.get_perspective_transform(src, dst)
        self.assertEqual(matrix.shape, (3, 3))

    def test_find_blocks_detects_square(self):
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[20:80, 20:80] = 255  # 60x60 white block, area 3600 > min_area
        objects = self.processor._find_blocks([mask], ["white"]) # pyright: ignore[reportPrivateUsage]
        self.assertEqual(len(objects), 1)
        self.assertEqual(objects[0].color, "white")

    def test_find_blocks_filters_small_contours(self):
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[0:5, 0:5] = 255  # area 25 < default min_area 120
        # pyright: ignore[reportPrivateUsage]
        objects = self.processor._find_blocks([mask], ["tiny"]) # pyright: ignore[reportPrivateUsage]
        self.assertEqual(objects, ())

    def test_find_blocks_empty_mask(self):
        mask = np.zeros((100, 100), dtype=np.uint8)
        # pyright: ignore[reportPrivateUsage]
        self.assertEqual(self.processor._find_blocks([mask], ["none"]), ())  # pyright: ignore[reportPrivateUsage]

    def test_perspective_transform_without_use_transform(self):
        contour = _square_contour(0, 0, 10)
        objects = self.processor._perspective_transform( # pyright: ignore[reportPrivateUsage]
            (("red", contour),),
        )
        self.assertEqual(len(objects), 1)
        self.assertEqual(objects[0].color, "red")

    def test_init_rejects_conflicting_transform_args(self):
        matrix = np.eye(3, dtype=np.float32)
        src = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float32)
        with self.assertRaises(ValueError):
            VisionProcessor(perspective_transform=matrix, src=src)

    def test_init_rejects_partial_src_dst(self):
        src = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float32)
        with self.assertRaises(ValueError):
            VisionProcessor(src=src)


class TestOpenChallengeVisionProcessor(unittest.TestCase):
    def setUp(self):
        self.processor = OpenChallengeVisionProcessor()

    def test_all_black_frame_is_fully_walled(self):
        frame = np.zeros((208, 512, 3), dtype=np.uint8)  # HSV value 0 -> black
        walls = self.processor.get_normalized_relative_wall_distances(frame)
        self.assertIsInstance(walls, OpenChallengeWalls)
        self.assertAlmostEqual(walls.left, 1.0)
        self.assertAlmostEqual(walls.right, 1.0)
        self.assertAlmostEqual(walls.center, 1.0)

    def test_all_white_frame_has_no_walls(self):
        # HSV value 255 -> not black
        frame = np.full((208, 512, 3), 255, dtype=np.uint8)
        walls = self.processor.get_normalized_relative_wall_distances(frame)
        self.assertAlmostEqual(walls.left, 0.0)
        self.assertAlmostEqual(walls.right, 0.0)
        self.assertAlmostEqual(walls.center, 0.0)

    def test_custom_rois_are_stored(self):
        left = np.s_[0:10, 0:10]
        processor = OpenChallengeVisionProcessor(left_wall_roi=left)
        self.assertEqual(processor.left_wall_roi, left)


class TestObstacleChallengeVisionProcessor(unittest.TestCase):
    def setUp(self):
        self.processor = ObstacleChallengeVisionProcessor()

    def test_get_segments_and_vertices(self):
        contour = _square_contour(0, 0, 10)
        vertices, p1, p2 = ObstacleChallengeVisionProcessor.get_segments_and_vertices(
            contour)
        self.assertEqual(vertices.shape, (4, 2))
        # p2 is p1 rolled by -1 (each edge's end point).
        np.testing.assert_array_equal(p2, np.roll(p1, -1, axis=0))

    def test_horizontal_distance(self):
        obj = VisionObject(contour=_square_contour(0, 0, 10), color="red")
        # A vertical line at x=200 should yield a distance of 195 from the centroid at x=5.
        self.assertEqual(self.processor.horizontal_distance(obj, 200), 195)
        # A horizontal line at the centroid x should yield zero distance.
        self.assertEqual(self.processor.horizontal_distance(obj, 5), 0)

    def test_all_black_frame_reports_infinite_walls(self):
        # A uniformly black frame yields a single wall contour (not two),
        # so one wall must be reported as infinite distance.
        frame = np.zeros((208, 512, 3), dtype=np.uint8)
        result = self.processor.get_walls_and_obstacles(frame)
        self.assertIsInstance(result, WallsAndObstacles)
        self.assertTrue(result.walls.left == float("inf")
                        or result.walls.right == float("inf"))

    def test_get_target_returns_none_without_obstacles(self):
        walls = ObstacleChallengeWalls(
            left=0, right=0, center=0, max_distance=1, center_area=1,
            left_raw=None, right_raw=None,
        )
        container = WallsAndObstacles(walls=walls, obstacles=None, parking_lot=ParkingLot(closer=None, further=None, max_x=1, max_y=1))
        self.assertIsNone(self.processor.get_target(container))

    def test_get_target_offset(self):
        walls = ObstacleChallengeWalls(
            left=0, right=0, center=0, max_distance=1, center_area=1,
            left_raw=None, right_raw=None,
        )
        obstacle_contour = _square_contour(100, 50, 20)
        obstacle = VisionObject(contour=obstacle_contour, color="red")
        container = WallsAndObstacles(walls=walls, obstacles=(obstacle,), parking_lot=ParkingLot(closer=None, further=None, max_x=1, max_y=1))
        target = self.processor.get_target(container)
        self.assertIsNotNone(target)

    def test_project_points_to_segments_shape(self):
        pts = np.array([[0, 0], [5, 5]], dtype=np.int32)
        seg_p1 = np.array([[0, 0], [10, 0]], dtype=np.int32)
        seg_p2 = np.array([[10, 0], [10, 10]], dtype=np.int32)
        result = ObstacleChallengeVisionProcessor._project_points_to_segments(  # pyright: ignore[reportPrivateUsage]
            pts, seg_p1, seg_p2)
        self.assertEqual(result.shape, (2, 2, 2))


if __name__ == "__main__":
    unittest.main()
