"""Requirement-focused tests for the obstacle challenge pipeline."""

from __future__ import annotations

import unittest
from pathlib import Path

from typing import Literal

from piclient.core.lib import GLOBAL_CONFIG
from piclient.core.vision import ParkingLot

from piclient.obstacle_challenge.transition_determinants import (
    should_avoid_obstacle,
    should_parallel_park,
    should_straight,
    should_turn,
)
from piclient.obstacle_challenge.video_tools import (
    OfflineObstacleChallengeStateMachine,
    default_output_paths,
    frame_timestamp,
)

from .obstacle_challenge_test_helpers import fixed_perf_counter, make_vision_object, make_walls_and_obstacles


class TestObstacleChallengeConfig(unittest.TestCase):
    def test_camera_shape_matches_derived_shm_size(self) -> None:
        camera = GLOBAL_CONFIG().CameraConfig
        self.assertEqual(camera.OUTPUT_SHAPE, (camera.OUTPUT_HEIGHT,
                         camera.OUTPUT_WIDTH, camera.OUTPUT_CHANNELS))
        self.assertEqual(camera.SHM_SIZE, camera.OUTPUT_WIDTH *
                         camera.OUTPUT_HEIGHT * camera.OUTPUT_CHANNELS)

    def test_default_output_paths(self) -> None:
        log_path, replay_path = default_output_paths(Path("/tmp/input.mp4"))
        self.assertEqual(log_path.name, "input_obstacle_challenge.pkl")
        self.assertEqual(replay_path.name,
                         "input_obstacle_challenge_replay.mp4")

    def test_frame_timestamp(self) -> None:
        self.assertAlmostEqual(frame_timestamp(
            GLOBAL_CONFIG().CameraConfig.FPS / 2, GLOBAL_CONFIG().CameraConfig.FPS), 0.5)
        self.assertAlmostEqual(frame_timestamp(
            0, GLOBAL_CONFIG().CameraConfig.FPS), 0.0)


class TestObstacleChallengeTransitions(unittest.TestCase):
    def test_offline_setup_uses_source_timestamp(self) -> None:
        state_machine = OfflineObstacleChallengeStateMachine(
            Path("/tmp/input.mp4"),
            Path("/tmp/output.pkl"),
        )
        state_machine.walls_and_obstacles = make_walls_and_obstacles(
            center_pixels=10.0)

        setattr(state_machine, "_frame_timestamp_s", 0.0)
        self.assertFalse(state_machine.handle_state_actions())

        setattr(state_machine, "_frame_timestamp_s", 12.0)
        self.assertFalse(state_machine.handle_state_actions())
        self.assertTrue(getattr(state_machine, "_setup_complete"))

    def test_transition_predicates(self) -> None:
        cfg = GLOBAL_CONFIG().SharedChallengeConfig
        straight_walls = make_walls_and_obstacles(center_pixels=10.0)
        turn_walls = make_walls_and_obstacles(center_pixels=100.0)
        obstacle_walls = make_walls_and_obstacles(
            center_pixels=10.0, obstacle_count=1)

        with fixed_perf_counter(cfg.TURN_COOLDOWN + 10.0):
            state_straight: Literal["straight"] = "straight"
            state_turn: Literal["turn"] = "turn"

            self.assertTrue(should_avoid_obstacle(
                obstacle_walls, state_straight, (10, 10), 1))
            self.assertFalse(should_avoid_obstacle(
                obstacle_walls, state_straight, None, 1))
            self.assertTrue(should_turn(turn_walls, state_straight, None, 1))
            self.assertFalse(should_turn(
                straight_walls, state_straight, None, 1))
            state_obstacle: Literal["obstacle_avoidance"] = "obstacle_avoidance"
            self.assertFalse(should_turn(
                turn_walls, state_obstacle, (10, 10), 1))
            self.assertTrue(should_avoid_obstacle(
                obstacle_walls, state_turn, (10, 10), 1))
            self.assertFalse(should_avoid_obstacle(
                obstacle_walls, state_obstacle, (10, 10), 1))
            self.assertTrue(should_straight(
                straight_walls, state_turn, None, 1))
            self.assertFalse(should_straight(turn_walls, state_turn, None, 1))

    def test_parallel_parking_entry_uses_normalized_marker_position(self) -> None:
        cfg = GLOBAL_CONFIG().ParallelParkingConfig
        parking_walls = make_walls_and_obstacles(
            center_pixels=10.0, obstacle_count=1)
        parking_walls.parking_lot = ParkingLot(
            closer=make_vision_object(100, 100, 20, "parking_lot"),
            further=None,
            max_x=GLOBAL_CONFIG().CameraConfig.OUTPUT_WIDTH,
            max_y=GLOBAL_CONFIG().CameraConfig.OUTPUT_HEIGHT,
        )
        parking_walls.parking_lot.closer.y_centroid = cfg.MIN_ENTRY_Y + 0.05
        self.assertTrue(should_parallel_park(
            parking_walls, "straight", None, 3))

        parking_walls.parking_lot.closer.y_centroid = cfg.MIN_ENTRY_Y - 0.05
        self.assertFalse(should_parallel_park(
            parking_walls, "straight", None, 3))
