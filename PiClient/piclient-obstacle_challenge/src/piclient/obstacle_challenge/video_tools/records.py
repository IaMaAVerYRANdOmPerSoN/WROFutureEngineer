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
    """Describe one motor command issued during an obstacle-challenge frame.

    The record preserves the requested signed speed, steering angle, and
    command duration so offline replay can show exactly what the controller
    submitted.

    :ivar speed: Signed motor speed requested by the controller.
    :ivar angle: Steering servo angle in degrees.
    :ivar duration: Duration for which the command should be applied, in
        seconds.
    """

    speed: float
    angle: float
    duration: float


@dataclass(slots=True)
class LogRecord:
    """Capture controller state, vision data, and telemetry for one frame.

    A :class:`LogRecord` is serialized sequentially by
    :class:`PickleLogWriter`. It combines the state-machine snapshot with the
    detected scene and the command generated for that frame, allowing replay
    code to reproduce both visual overlays and control decisions.

    :ivar frame_index: Zero-based source-frame index.
    :ivar timestamp_s: Frame timestamp in seconds from the source-video clock.
    :ivar state: State-machine state active for the frame.
    :ivar turn_counter: Number of completed turns at the frame.
    :ivar last_turn_time_s: Timestamp of the most recent completed turn.
    :ivar start_time_s: Challenge start timestamp, or ``None`` before startup.
    :ivar target: Selected target point as ``(x, y)``, or ``None``.
    :ivar obstacle_count: Number of obstacles detected in the frame.
    :ivar walls_and_obstacles: Full vision result, or ``None`` if unavailable.
    :ivar wall_error: Wall-following error used by the controller.
    :ivar turn_correction: Turn correction calculated for the frame.
    :ivar corner_turn_correction: Corner-turn correction calculated for the
        frame.
    :ivar obstacle_avoidance_correction: Obstacle-avoidance correction.
    :ivar command: Motor command selected for the frame.
    :ivar command_submitted: Whether a new command was submitted in the frame.
    :ivar finished: Whether the challenge completed in the frame.
    """

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
    """Append :class:`LogRecord` objects to a pickle stream.

    The writer creates parent directories when entered, appends records using
    the highest available pickle protocol, and flushes after every write so a
    partially completed offline run remains readable.

    :ivar log_path: Destination path for the append-only pickle stream.
    :ivar _fp: Open binary stream, or ``None`` while the writer is closed.
    """

    def __init__(self, log_path: Path) -> None:
        """Create a closed writer for *log_path*.

        :param log_path: File path where serialized records will be appended.
        :returns: ``None``.
        :rtype: None
        """
        self.log_path = log_path
        self._fp: BinaryIO | None = None

    def __enter__(self) -> "PickleLogWriter":
        """Open the destination stream and return this writer.

        :returns: This open :class:`PickleLogWriter` instance.
        :rtype: PickleLogWriter
        """
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._fp = self.log_path.open("ab")
        return self

    def __exit__(self, exc_type: type[BaseException], exc_value: BaseException, traceback: object) -> None:
        """Close the stream when leaving a writer context.

        :param exc_type: Exception class raised inside the context, or
            ``None`` when it exited normally.
        :param exc_value: Exception instance raised inside the context, or
            ``None`` when it exited normally.
        :param traceback: Traceback object for the context exception, or
            ``None`` when it exited normally.
        :returns: ``None``; exceptions are not suppressed.
        :rtype: None
        """
        self.close()

    def write(self, record: LogRecord) -> None:
        """Serialize and flush one telemetry record.

        :param record: Frame telemetry to append to the pickle stream.
        :raises RuntimeError: If the writer has not been entered or was
            already closed.
        :returns: ``None``.
        :rtype: None
        """
        if self._fp is None:
            raise RuntimeError("PickleLogWriter is not open")

        pickle.dump(record, self._fp, protocol=pickle.HIGHEST_PROTOCOL)
        self._fp.flush()

    def close(self) -> None:
        """Flush and close the stream if it is open.

        Calling this method more than once is harmless.

        :returns: ``None``.
        :rtype: None
        """
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
    """Build a normalized telemetry record from one controller update.

    Floating-point timestamps and correction values are rounded to six decimal
    places for stable serialized output. The obstacle count is derived from
    *walls_and_obstacles* so callers cannot accidentally record a stale count.

    :param frame_index: Source-frame index associated with the update.
    :param timestamp_s: Frame timestamp in seconds.
    :param state: Active obstacle-challenge state.
    :param turn_counter: Number of turns completed so far.
    :param last_turn_time_s: Timestamp of the most recent completed turn.
    :param start_time_s: Challenge start timestamp, or ``None``.
    :param target: Selected target point as ``(x, y)``, or ``None``.
    :param walls_and_obstacles: Vision result containing wall and obstacle
        detections, or ``None``.
    :param wall_error: Wall-following controller error.
    :param turn_correction: Turn correction for this frame.
    :param corner_turn_correction: Corner-turn correction for this frame.
    :param obstacle_avoidance_correction: Obstacle-avoidance correction.
    :param command: Motor command selected for the frame.
    :param command_submitted: Whether the command was sent to the executor.
    :param finished: Whether processing completed at this frame.
    :returns: A serializable :class:`LogRecord` containing the supplied and
        derived telemetry.
    :rtype: LogRecord
    """
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