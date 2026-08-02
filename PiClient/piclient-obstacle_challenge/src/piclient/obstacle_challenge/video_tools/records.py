"""Shared telemetry records and pickle logging helpers for obstacle-challenge videos."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import pickle
from typing import BinaryIO

from piclient.core.vision import WallsAndObstacles

from ..transition_determinants import ChallengeState


@dataclass(slots=True)
class DriveCommand:
    speed: float
    angle: float
    duration: float


@dataclass(slots=True)
class LogRecord:
    frame_index: int
    timestamp_s: float
    state: ChallengeState
    turn_counter: int
    last_turn_time_s: float
    start_time_s: float | None
    target: tuple[int, int] | None
    obstacle_count: int
    walls_and_obstacles: WallsAndObstacles | None
    wall_error: float
    turn_correction: float
    corner_turn_correction: float
    obstacle_avoidance_correction: float
    command: DriveCommand
    command_submitted: bool
    finished: bool


class PickleLogWriter:
    """Append LogRecord objects to a pickle stream."""

    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        self._fp: BinaryIO | None = None

    def __enter__(self) -> "PickleLogWriter":
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._fp = self.log_path.open("ab")
        return self

    def __exit__(self, exc_type: type[BaseException], exc_value: BaseException, traceback: object) -> None:
        self.close()

    def write(self, record: LogRecord) -> None:
        if self._fp is None:
            raise RuntimeError("PickleLogWriter is not open")

        pickle.dump(record, self._fp, protocol=pickle.HIGHEST_PROTOCOL)
        self._fp.flush()

    def close(self) -> None:
        if self._fp is not None:
            self._fp.close()
            self._fp = None


def build_log_record(
    *,
    frame_index: int,
    timestamp_s: float,
    state: ChallengeState,
    turn_counter: int,
    last_turn_time_s: float,
    start_time_s: float | None,
    target: tuple[int, int] | None,
    walls_and_obstacles: WallsAndObstacles | None,
    wall_error: float,
    turn_correction: float,
    corner_turn_correction: float,
    obstacle_avoidance_correction: float,
    command: DriveCommand,
    command_submitted: bool,
    finished: bool,
) -> LogRecord:
    obstacle_count = 0
    if walls_and_obstacles is not None and walls_and_obstacles.obstacles is not None:
        obstacle_count = len(walls_and_obstacles.obstacles)

    return LogRecord(
        frame_index=frame_index,
        timestamp_s=round(timestamp_s, 6),
        state=state,
        turn_counter=turn_counter,
        last_turn_time_s=round(last_turn_time_s, 6),
        start_time_s=None if start_time_s is None else round(start_time_s, 6),
        target=target,
        obstacle_count=obstacle_count,
        walls_and_obstacles=walls_and_obstacles,
        wall_error=round(wall_error, 6),
        turn_correction=round(turn_correction, 6),
        corner_turn_correction=round(corner_turn_correction, 6),
        obstacle_avoidance_correction=round(obstacle_avoidance_correction, 6),
        command=command,
        command_submitted=command_submitted,
        finished=finished,
    )