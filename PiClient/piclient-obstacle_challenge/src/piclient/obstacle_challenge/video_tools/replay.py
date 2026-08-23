"""Replay rendering for obstacle-challenge videos."""
from typing import Any

from pathlib import Path
from collections.abc import Sequence
import pickle

import cv2
import numpy as np
from loguru import logger

from piclient.core.lib import GLOBAL_CONFIG
from piclient.core.vision import VisionObject

from .records import LogRecord

# Number of extra rows reserved below the cropped frame for textual overlays
PAD_ROWS = 700


def load_log_records(log_path: Path) -> list[LogRecord]:
    """Load valid :class:`LogRecord` objects from a pickle stream.

    Records of other types are skipped with a warning, while end-of-file marks
    the normal end of the append-only stream.

    :param log_path: Pickle stream containing serialized telemetry records.
    :returns: Valid records in their original stream order.
    :rtype: list[LogRecord]
    """
    records: list[LogRecord] = []
    with log_path.open("rb") as log_fp:
        while True:
            try:
                record: LogRecord | Any = pickle.load(log_fp)
            except EOFError:
                break

            if isinstance(record, LogRecord):
                records.append(record)
            else:
                logger.warning(f"Skipping invalid log record: {record}")
    return records


def _format_obstacles(obstacles: Sequence[VisionObject] | None) -> str:
    """Format obstacle detections as an indented replay text block.

    :param obstacles: Detected objects to describe, or ``None`` when no
        obstacle result is available.
    :returns: Human-readable obstacle details for an overlay.
    :rtype: str
    """
    if obstacles is None:
        return "    Obstacles: None\n"
    result = "    Obstacles: [\n"
    for i, obstacle in enumerate(obstacles):
        result += (
            f"        {i}\n"
            f"            Contour: {obstacle.contour}\n"
            f"            Color: {obstacle.color}\n"
            f"            Bounding Box: {obstacle.bbox}\n"
            f"            X Centroid: {obstacle.x_centroid}\n"
            f"            Y Centroid: {obstacle.y_centroid}\n"
        )
    result += "    ]\n"
    return result


def format_log_record(record: LogRecord) -> str:
    """Format one telemetry record for display beneath a replay frame.

    :param record: Telemetry snapshot to render.
    :returns: Multiline text containing state, vision, correction, and command
        information.
    :rtype: str
    """
    res = (
        f"Frame: {record.frame_index}\n"
        f"Replay Timestamp: {record.timestamp_s:.3f}s\n"
        f"State: {record.state}\n"
        f"Turn Count: {record.turn_counter}\n"
        f"Last Turn Time: {record.last_turn_time_s:.3f}s\n"
        f"Final Straight Start Time: {f'{record.start_time_s:.3f}s' if record.start_time_s is not None else 'None'}\n"
        f"Target: {record.target}\n"
        f"Obstacle Count: {record.obstacle_count}\n"
    )
    res += (
        f"Walls and Obstacles\n"
        f"    Left Wall: {record.walls_and_obstacles.walls.left:.3f}\n"
        f"    Right Wall: {record.walls_and_obstacles.walls.right:.3f}\n"
        f"    Top Wall: {record.walls_and_obstacles.walls.center:.3f}\n"
        f"{_format_obstacles(record.walls_and_obstacles.obstacles)}"
    ) if record.walls_and_obstacles is not None else ""
    res += (
        f"Wall Error: {record.wall_error:.3f}\n"
        f"Turn Correction: {record.turn_correction:.3f}\n"
        f"Corner Turn Correction: {record.corner_turn_correction:.3f}\n"
        f"Obstacle Avoidance Correction: {record.obstacle_avoidance_correction:.3f}\n"
        f"Command: \n"
        f"    speed: {record.command.speed:.3f}\n"
        f"    angle: {record.command.angle:.3f}\n"
        f"    duration: {record.command.duration:.3f}\n"
    )
    return res


def draw_replay_overlay(frame: np.ndarray, record: LogRecord) -> np.ndarray:
    """Draw detections, target, steering, and telemetry over a camera frame.

    The returned image includes additional black rows below the original frame
    for the textual record details; the input array is never modified.

    :param frame: Cropped BGR camera frame with the configured output shape.
    :param record: Telemetry and vision data to visualize.
    :returns: Copy of *frame* with graphical and textual annotations.
    :rtype: numpy.ndarray
    """
    # The caller should pass a frame that is already cropped to the
    # camera output shape.
    overlay = frame.copy()

    if record.walls_and_obstacles is not None:
        if record.walls_and_obstacles.walls.left_raw is not None:
            cv2.drawContours(overlay, [record.walls_and_obstacles.walls.left_raw.contour], -1, (0, 255, 0), 2)
        if record.walls_and_obstacles.walls.right_raw is not None:
            cv2.drawContours(overlay, [record.walls_and_obstacles.walls.right_raw.contour], -1, (0, 255, 0), 2)

        if record.walls_and_obstacles.obstacles is not None:
            for obstacle in record.walls_and_obstacles.obstacles:
                cv2.drawContours(overlay, [obstacle.contour], -1, (0, 0, 255), 2)

    c_roi = GLOBAL_CONFIG().VisionConfig.CENTER_WALL_ROI
    cv2.rectangle(
        overlay,
        (c_roi[1].start, c_roi[0].start),
        (c_roi[1].stop, c_roi[0].stop),
        (0, 255, 0),
        2,
    )

    cv2.circle(overlay, (int(record.target[0]), int(record.target[1])), 5, (0, 0, 255), -1) if record.target is not None else None

    height, width = overlay.shape[:2]
    center_x = width // 2
    bottom_y = height - 1
    normalized = (record.command.angle - 90.0) / 90.0
    line_length = max(40, width // 4)
    x_offset = int(normalized * line_length)
    cv2.line(overlay, (center_x, bottom_y), (center_x + x_offset, max(0, bottom_y - line_length // 2)), (0, 255, 0), 2)
    cv2.circle(overlay, (center_x, bottom_y), 4, (0, 255, 0), -1)

    padded_overlay = np.zeros((overlay.shape[0] + PAD_ROWS, overlay.shape[1], overlay.shape[2]), dtype=np.uint8)
    padded_overlay[:overlay.shape[0], :, :] = overlay

    cv2.putText(
        padded_overlay,
        format_log_record(record),
        (10, 250),
        cv2.FONT_HERSHEY_PLAIN,
        0.9,
        (0, 255, 255),
        1,
        cv2.LINE_AA,
    )

    return padded_overlay


def replay_video(video_path: Path, log_path: Path, output_video: Path | None = None, display: bool = False) -> Path:
    """Replay a source video with synchronized overlay annotations.

    Each source frame is paired with its corresponding log record and written
    to an output video. The output defaults to a replay filename beside the
    source video.

    :param video_path: Source video to decode.
    :param log_path: Pickle telemetry stream produced during processing.
    :param output_video: Destination video path, or ``None`` for the default.
    :param display: Whether to show the replay interactively while rendering.
    :returns: Path to the rendered replay video.
    :rtype: pathlib.Path
    :raises RuntimeError: If no records or the source video cannot be opened.
    """
    records = load_log_records(log_path)
    if not records:
        raise RuntimeError(f"No log records found in {log_path}")

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open replay video: {video_path}")

    video_fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    if video_fps <= 0:
        video_fps = GLOBAL_CONFIG().CameraConfig.FPS

    output_video = output_video or video_path.with_name(f"{video_path.stem}_replay.mp4")
    ok, frame = capture.read()
    if not ok:
        capture.release()
        raise RuntimeError(f"Could not read any frames from replay video: {video_path}")

    record_index = 0
    current_record = records[0]

    logger.info(format_log_record(current_record))

    # The recording now already stores the cropped camera output, so size
    # the writer directly from the incoming frame shape (width, height + PAD_ROWS).
    cropped_shape = frame.shape
    writer = cv2.VideoWriter(
        str(output_video),
        cv2.VideoWriter.fourcc(*"mp4v"),
        video_fps,
        frameSize=(int(cropped_shape[1]), int(cropped_shape[0] + PAD_ROWS)),
    )
    if not writer.isOpened():
        capture.release()
        raise RuntimeError(f"Could not open replay output for writing: {output_video}")

    frame_index = 0

    try:
        writer.write(draw_replay_overlay(frame, current_record))
        if display:
            cv2.imshow("Obstacle Challenge Replay", draw_replay_overlay(frame, current_record))
            delay_ms = max(1, int(1000 / video_fps))
            if cv2.waitKey(delay_ms) & 0xFF in (ord("q"), 27):
                return output_video

        frame_index = 1
        while True:
            ok, frame = capture.read()
            if not ok:
                break

            playback_time_s = frame_index / video_fps
            while record_index + 1 < len(records):
                next_record = records[record_index + 1]
                if next_record.timestamp_s > playback_time_s:
                    break
                record_index += 1
                current_record = next_record
                #logger.info(format_log_record(current_record))

            overlay = draw_replay_overlay(frame, current_record)
            writer.write(overlay)

            if display:
                cv2.imshow("Obstacle Challenge Replay", overlay)
                delay_ms = max(1, int(1000 / video_fps))
                if cv2.waitKey(delay_ms) & 0xFF in (ord("q"), 27):
                    break

            frame_index += 1
    finally:
        capture.release()
        writer.release()
        if display:
            cv2.destroyAllWindows()

    return output_video