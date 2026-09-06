"""Integration tests for obstacle-challenge video processing and replay."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import cv2

from piclient.core.lib import GLOBAL_CONFIG

from piclient.obstacle_challenge.video_tools import format_log_record, load_log_records, process_video, replay_video

from .obstacle_challenge_test_helpers import make_log_record, make_walls_and_obstacles, write_test_video


class TestObstacleChallengeVideoTools(unittest.TestCase):
    def test_format_log_record_includes_parking_lot_data(self) -> None:
        formatted = format_log_record(make_log_record(walls_and_obstacles=make_walls_and_obstacles(center_pixels=0.0)))

        self.assertIn("Parking Lot:", formatted)
        self.assertIn("Closer: None", formatted)
        self.assertIn("Further: None", formatted)

    def test_process_and_replay_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            input_video = write_test_video(tmp_path / "obstacle_fixture.mp4", frame_count=3)
            output_log = tmp_path / "obstacle_fixture.pkl"
            output_replay = tmp_path / "obstacle_fixture_replay.mp4"

            replay_path = process_video(input_video, output_log, output_replay, display=False)
            self.assertEqual(replay_path, output_replay)
            self.assertTrue(output_log.exists())
            self.assertTrue(output_replay.exists())

            records = load_log_records(output_log)
            self.assertGreaterEqual(len(records), 1)

            capture = cv2.VideoCapture(str(output_replay))
            try:
                self.assertTrue(capture.isOpened())
                ok, frame = capture.read()
                self.assertTrue(ok)
                expected_height = GLOBAL_CONFIG().CameraConfig.OUTPUT_HEIGHT + 700
                self.assertEqual(frame.shape, (expected_height, GLOBAL_CONFIG().CameraConfig.OUTPUT_WIDTH, 3))
            finally:
                capture.release()

            replay_path_2 = replay_video(input_video, output_log, output_video=tmp_path / "obstacle_fixture_replay_2.mp4", display=False)
            self.assertTrue(replay_path_2.exists())