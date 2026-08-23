"""Shared helpers for obstacle-challenge tests."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from collections.abc import Generator
import importlib

import cv2
import numpy as np

from piclient.core.lib import GLOBAL_CONFIG
from piclient.core.vision import ObstacleChallengeWalls, VisionObject, WallsAndObstacles, ParkingLot

from piclient.obstacle_challenge.transition_determinants import ChallengeState
from piclient.obstacle_challenge.video_tools.records import DriveCommand, LogRecord


def square_contour(x0: int, y0: int, size: int) -> np.ndarray:
    """Return an OpenCV contour for an axis-aligned square."""
    return np.array(
        [[[x0, y0]], [[x0 + size, y0]], [[x0 + size, y0 + size]], [[x0, y0 + size]]],
        dtype=np.int32,
    )


def make_vision_object(x0: int, y0: int, size: int, color: str) -> VisionObject:
    """Build a simple square VisionObject for obstacle-challenge tests."""
    return VisionObject(contour=square_contour(x0, y0, size), color=color)


def make_walls_and_obstacles(*, center_pixels: float, obstacle_count: int = 0) -> WallsAndObstacles:
    """Build a minimal WallsAndObstacles object with optional obstacles."""
    width = GLOBAL_CONFIG().CameraConfig.OUTPUT_WIDTH
    height = GLOBAL_CONFIG().CameraConfig.OUTPUT_HEIGHT

    left_raw = make_vision_object(0, 0, 40, "walls")
    right_raw = make_vision_object(width - 40, 0, 40, "walls")
    walls = ObstacleChallengeWalls(
        left=40,
        right=40,
        center=center_pixels,
        max_distance=width / 2,
        center_area=100.0,
        left_raw=left_raw,
        right_raw=right_raw,
    )

    obstacles: tuple[VisionObject, ...] | None = None
    if obstacle_count > 0:
        obstacle_list: list[VisionObject] = []
        start_x = width // 2 - 40
        start_y = height // 2 - 20
        for index in range(obstacle_count):
            obstacle_list.append(make_vision_object(start_x + index * 10, start_y, 30, "red"))
        obstacles = tuple(obstacle_list)

    return WallsAndObstacles(walls=walls, obstacles=obstacles, parking_lot=ParkingLot(closer=None, further=None, max_x=width, max_y=height))


def make_drive_command(speed: float = 0.0, angle: float = 90.0, duration: float = 0.0) -> DriveCommand:
    return DriveCommand(speed=speed, angle=angle, duration=duration)


def make_log_record(
    *,
    frame_index: int = 0,
    timestamp_s: float = 0.0,
    state: ChallengeState = "straight",
    turn_counter: int = 0,
    last_turn_time_s: float = 0.0,
    start_time_s: float | None = None,
    target: tuple[int, int] | None = None,
    walls_and_obstacles: WallsAndObstacles | None = None,
    wall_error: float = 0.0,
    turn_correction: float = 90.0,
    corner_turn_correction: float = 90.0,
    obstacle_avoidance_correction: float = 90.0,
    command: DriveCommand | None = None,
    command_submitted: bool = False,
    finished: bool = False,
) -> LogRecord:
    """Build a serialisable log record for replay tests."""
    if command is None:
        command = make_drive_command()

    return LogRecord(
        frame_index=frame_index,
        timestamp_s=timestamp_s,
        state=state,
        turn_counter=turn_counter,
        last_turn_time_s=last_turn_time_s,
        start_time_s=start_time_s,
        target=target,
        obstacle_count=0 if walls_and_obstacles is None or walls_and_obstacles.obstacles is None else len(walls_and_obstacles.obstacles),
        walls_and_obstacles=walls_and_obstacles,
        wall_error=wall_error,
        turn_correction=turn_correction,
        corner_turn_correction=corner_turn_correction,
        obstacle_avoidance_correction=obstacle_avoidance_correction,
        command=command,
        command_submitted=command_submitted,
        finished=finished,
    )


def write_test_video(path: Path, *, frame_count: int = 3) -> Path:
    """Write a tiny synthetic obstacle-challenge video fixture."""
    width = GLOBAL_CONFIG().CameraConfig.OUTPUT_WIDTH
    height = GLOBAL_CONFIG().CameraConfig.OUTPUT_HEIGHT
    fourcc = cv2.VideoWriter.fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, GLOBAL_CONFIG().CameraConfig.FPS, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"Could not open synthetic video fixture for writing: {path}")

    for frame_index in range(frame_count):
        frame = np.full((height, width, 3), 255, dtype=np.uint8)
        cv2.rectangle(frame, (0, 0), (35, height - 1), (0, 0, 0), -1)
        cv2.rectangle(frame, (width - 35, 0), (width - 1, height - 1), (0, 0, 0), -1)

        obstacle_x = width // 2 - 25 + frame_index * 3
        cv2.rectangle(frame, (obstacle_x, height // 2 - 18), (obstacle_x + 30, height // 2 + 18), (0, 0, 255), -1)
        writer.write(frame)

    writer.release()
    return path


@contextmanager
def fixed_perf_counter(timestamp_s: float) -> Generator[None, None, None]:
    """Temporarily replace the obstacle-challenge perf counters with a fixed time."""
    transition_determinants = importlib.import_module("piclient.obstacle_challenge.transition_determinants")
    obstacle_challenge_module = importlib.import_module("piclient.obstacle_challenge.obstacle_challenge")

    original_transition_perf_counter = getattr(transition_determinants, "perf_counter")
    original_state_machine_perf_counter = getattr(obstacle_challenge_module, "perf_counter")

    setattr(transition_determinants, "perf_counter", lambda: timestamp_s)
    setattr(obstacle_challenge_module, "perf_counter", lambda: timestamp_s)
    try:
        yield
    finally:
        setattr(transition_determinants, "perf_counter", original_transition_perf_counter)
        setattr(obstacle_challenge_module, "perf_counter", original_state_machine_perf_counter)