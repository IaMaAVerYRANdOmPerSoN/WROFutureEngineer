"""Requirement-focused tests for the obstacle challenge pipeline."""

from __future__ import annotations

import unittest
from pathlib import Path

from typing import Literal

from piclient.core.lib import GLOBAL_CONFIG

from piclient.obstacle_challenge.transition_determinants import (
    should_avoid_obstacle,
    should_final_straight_and_parking,
    should_final_turn,
    should_straight,
    should_turn,
)
from piclient.obstacle_challenge.video_tools import default_output_paths, frame_timestamp

from .obstacle_challenge_test_helpers import fixed_perf_counter, make_walls_and_obstacles


class TestObstacleChallengeConfig(unittest.TestCase):
    def test_camera_shape_matches_derived_shm_size(self) -> None:
        camera = GLOBAL_CONFIG().CameraConfig
        self.assertEqual(camera.OUTPUT_SHAPE, (camera.OUTPUT_HEIGHT, camera.OUTPUT_WIDTH, camera.OUTPUT_CHANNELS))
        self.assertEqual(camera.SHM_SIZE, camera.OUTPUT_WIDTH * camera.OUTPUT_HEIGHT * camera.OUTPUT_CHANNELS)
        self.assertEqual(camera.OUTPUT_HEIGHT, 208)
        self.assertEqual(camera.OUTPUT_WIDTH, 512)

    def test_default_output_paths(self) -> None:
        log_path, replay_path = default_output_paths(Path("/tmp/input.mp4"))
        self.assertEqual(log_path.name, "input_obstacle_challenge.pkl")
        self.assertEqual(replay_path.name, "input_obstacle_challenge_replay.mp4")

    def test_frame_timestamp(self) -> None:
        self.assertAlmostEqual(frame_timestamp(int(GLOBAL_CONFIG().CameraConfig.FPS // 2), GLOBAL_CONFIG().CameraConfig.FPS), 0.5)
        self.assertAlmostEqual(frame_timestamp(0, GLOBAL_CONFIG().CameraConfig.FPS), 0.0)


class TestObstacleChallengeTransitions(unittest.TestCase):
    def test_transition_predicates(self) -> None:
        cfg = GLOBAL_CONFIG().SharedChallengeConfig
        straight_walls = make_walls_and_obstacles(center_pixels=10.0)
        turn_walls = make_walls_and_obstacles(center_pixels=100.0)
        obstacle_walls = make_walls_and_obstacles(center_pixels=10.0, obstacle_count=1)

        with fixed_perf_counter(cfg.TURN_COOLDOWN + 10.0):
            state_straight: Literal["straight"] = "straight"
            state_turn: Literal["turn"] = "turn"
            state_final_turn: Literal["final_turn"] = "final_turn"

            self.assertTrue(should_avoid_obstacle(obstacle_walls, state_straight, (10, 10), 0.0, 0, None))
            self.assertFalse(should_avoid_obstacle(obstacle_walls, state_straight, None, 0.0, 0, None))
            self.assertTrue(should_turn(turn_walls, state_straight, None, 0.0, 0, None))
            self.assertFalse(should_turn(straight_walls, state_straight, None, 0.0, 0, None))
            self.assertTrue(should_straight(straight_walls, state_turn, None, 0.0, 0, None))
            self.assertFalse(should_straight(turn_walls, state_turn, None, 0.0, 0, None))
            self.assertTrue(should_final_turn(turn_walls, state_straight, None, 0.0, cfg.LAP_LENGTH_IN_TURNS, None))
            self.assertFalse(should_final_turn(turn_walls, state_final_turn, None, 0.0, cfg.LAP_LENGTH_IN_TURNS, None))
            self.assertTrue(should_final_straight_and_parking(straight_walls, state_final_turn, None, 0.0, 0, 1.0))
            self.assertFalse(should_final_straight_and_parking(turn_walls, state_final_turn, None, 0.0, 0, 1.0))