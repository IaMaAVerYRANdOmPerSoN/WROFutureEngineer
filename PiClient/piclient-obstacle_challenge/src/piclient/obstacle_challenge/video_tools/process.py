"""Source-video processing for obstacle-challenge runs."""

from __future__ import annotations

from pathlib import Path
from contextlib import contextmanager
from time import sleep
from typing import Self, cast

import asyncio
import cv2
import numpy as np
from loguru import logger
from multiprocessing import shared_memory
from multiprocessing.connection import Connection

from piclient.core.interface import DriveCommandExecutor
from piclient.core.lib import GLOBAL_CONFIG, ProcessContextManager, TransitionManager
from piclient.core.vision import (
    AsyncMultiprocessingVisionProcessor,
    ObstacleChallengeAsyncMultiprocessingVisionProcessor,
    WallsAndObstacles,
)

from ..obstacle_challenge import ObstacleChallengeStateMachine
from ..transition_determinants import (
    TypedTranisitionManager,
    should_avoid_obstacle,
    should_final_straight,
    should_final_turn,
    should_straight,
    should_turn,
)
from .records import DriveCommand, PickleLogWriter, build_log_record
from .replay import replay_video


class OfflineObstacleChallengeVisionProcessor(ObstacleChallengeAsyncMultiprocessingVisionProcessor):
    async_pipe_reader = staticmethod(AsyncMultiprocessingVisionProcessor.async_pipe_reader_fifo)


class VideoFileCameraSource:
    """Camera-process target that replays a video file into shared memory."""

    def __init__(self, video_path: Path) -> None:
        self.video_path = video_path

    def __call__(self, shm_name: str, *senders: Connection) -> None:
        capture = cv2.VideoCapture(str(self.video_path))
        if not capture.isOpened():
            raise RuntimeError(f"Could not open input video: {self.video_path}")

        shm = shared_memory.SharedMemory(name=shm_name)
        height = GLOBAL_CONFIG().CameraConfig.OUTPUT_HEIGHT
        width = GLOBAL_CONFIG().CameraConfig.OUTPUT_WIDTH

        try:
            shared_frame = np.ndarray((height, width, 3), dtype=np.uint8, buffer=shm.buf)
            while True:
                ok, frame = capture.read()
                if not ok:
                    break

                if frame.shape[:2] != (height, width):
                    frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)

                np.copyto(shared_frame, frame.astype(np.uint8, copy=False))
                for sender in senders:
                    sender.send(True)
                sleep(0.033)
        finally:
            capture.release()
            shm.close()
            return


class RecordingDriveCommandExecutor:
    """In-memory stand-in used by offline source-video processing."""

    def __init__(self) -> None:
        self.latest_command = DriveCommand(0.0, 90.0, 0.0)
        self.command_submitted = False

    async def __aenter__(self) -> "RecordingDriveCommandExecutor":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def reload(self) -> "RecordingDriveCommandExecutor":
        return self

    def submit(self, speed: float, angle: float, duration: float) -> None:
        self.latest_command = DriveCommand(speed, angle, duration)
        self.command_submitted = True


def default_output_paths(input_video: Path) -> tuple[Path, Path]:
    stem = input_video.with_suffix("")
    return (
        stem.with_name(f"{stem.name}_obstacle_challenge.pkl"),
        stem.with_name(f"{stem.name}_obstacle_challenge_replay.mp4"),
    )


def frame_timestamp(frame_index: int, fps: float) -> float:
    return frame_index / fps if fps > 0 else frame_index / GLOBAL_CONFIG().CameraConfig.FPS


def build_transition_manager() -> TypedTranisitionManager:
    return TransitionManager(
        hysteresis_values=[GLOBAL_CONFIG().SharedChallengeConfig.HYSTERESIS] * 5,
        priorities=[2, 1, 3, 4, 0],
        obstacle_avoidance=should_avoid_obstacle,
        straight=should_straight,
        turn=should_turn,
        final_turn=should_final_turn,
        final_straight=should_final_straight,
    )


class OfflineObstacleChallengeStateMachine(ObstacleChallengeStateMachine):
    def __init__(self, input_video: Path, telemetry_log: Path) -> None:
        self._frame_timestamp_s = 0.0
        self.frame_index = 0
        self._telemetry_log = telemetry_log
        self._telemetry_writer = PickleLogWriter(self._telemetry_log)
        self._recording_executor = RecordingDriveCommandExecutor()
        self._process_manager = ProcessContextManager(
            camera_callback=VideoFileCameraSource(input_video),
            vision_callback=OfflineObstacleChallengeVisionProcessor.vision_process_context_manager,
        )
        self.output_stream = None
        self.shm = None
        super().__init__(
            initial_state="straight",
            transition_manager=build_transition_manager(),
            drive_command_executor=cast(DriveCommandExecutor, self._recording_executor),
        )

    @property
    def recording_executor(self) -> RecordingDriveCommandExecutor:
        return self._recording_executor

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        try:
            self._process_manager.__enter__()
            output_stream = self._process_manager.output_stream
            if output_stream is None:
                raise RuntimeError("Output stream is not initialized")
            self.output_stream = AsyncMultiprocessingVisionProcessor.async_pipe_reader_fifo(output_stream)
            self.shm = self._process_manager.shm
            self._telemetry_writer.__enter__()
            return self
        except Exception:
            self._process_manager.__exit__(Exception, Exception(), None)
            await super().__aexit__(Exception, Exception(), None)
            raise

    async def __aexit__(self, exc_type: type[BaseException], exc_value: BaseException, traceback: object) -> None:
        self._telemetry_writer.__exit__(exc_type, exc_value, traceback)
        self._process_manager.__exit__(exc_type, exc_value, traceback)
        await super().__aexit__(exc_type, exc_value, traceback)

    def _write_state_telemetry(self, timestamp_s: float, finished: bool) -> None:
        walls_and_obstacles = self.walls_and_obstacles
        record = build_log_record(
            frame_index=self.frame_index,
            timestamp_s=timestamp_s,
            state=self.current_state,
            turn_counter=self.turn_counter,
            last_turn_time_s=self.last_turn_time,
            start_time_s=self.start_time,
            target=self.target_position,
            walls_and_obstacles=walls_and_obstacles,
            wall_error=self.wall_error,
            turn_correction=self.turn_correction,
            corner_turn_correction=self.corner_turn_correction,
            obstacle_avoidance_correction=self.obstacle_avoidance_correction,
            command=self.recording_executor.latest_command,
            command_submitted=self.recording_executor.command_submitted,
            finished=finished,
        )
        self._telemetry_writer.write(record)
        self.recording_executor.command_submitted = False

    def step(
        self,
        walls_and_obstacles: WallsAndObstacles,
        target_position: tuple[int, int] | None,
        timestamp_s: float,
    ) -> bool:
        self._frame_timestamp_s = timestamp_s
        self.frame_index += 1
        with _video_clock(timestamp_s):
            super().update(walls_and_obstacles, target_position)
            finished = super().handle_state_actions()

        self._write_state_telemetry(timestamp_s, finished)
        return finished


@contextmanager
def _video_clock(timestamp_s: float):
    import piclient.obstacle_challenge.transition_determinants as transition_determinants
    import piclient.obstacle_challenge.obstacle_challenge as obstacle_challenge_module

    original_perf_counter = transition_determinants.__dict__["perf_counter"]
    original_state_machine_perf_counter = obstacle_challenge_module.__dict__["perf_counter"]

    setattr(transition_determinants, "perf_counter", lambda: timestamp_s)
    setattr(obstacle_challenge_module, "perf_counter", lambda: timestamp_s)
    try:
        yield
    finally:
        transition_determinants.__dict__["perf_counter"] = original_perf_counter
        obstacle_challenge_module.__dict__["perf_counter"] = original_state_machine_perf_counter


def process_video(input_video: Path, output_log: Path, output_replay: Path, display: bool = False) -> Path:
    """Run the obstacle challenge pipeline on a video file and render a replay."""
    output_log.parent.mkdir(parents=True, exist_ok=True)
    output_replay.parent.mkdir(parents=True, exist_ok=True)

    async def _run() -> None:
        source_capture = cv2.VideoCapture(str(input_video))
        if not source_capture.isOpened():
            raise RuntimeError(f"Could not open input video: {input_video}")

        source_fps = float(source_capture.get(cv2.CAP_PROP_FPS) or 0.0)
        if source_fps <= 0:
            source_fps = GLOBAL_CONFIG().CameraConfig.FPS
        source_frame_count = int(source_capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        source_capture.release()

        async with OfflineObstacleChallengeStateMachine(input_video, output_log) as state_machine:
            frame_index = 0

            if state_machine.output_stream is None:
                raise RuntimeError("Output stream is not initialized")
            if state_machine.shm is None:
                raise RuntimeError("Shared memory is not initialized")

            async for walls_and_obstacles, target in state_machine.output_stream:
                timestamp_s = frame_timestamp(frame_index, source_fps)

                finished = state_machine.step(walls_and_obstacles, target, timestamp_s)

                if finished:
                    logger.success("Finished source-video obstacle challenge processing")
                    break

                if source_frame_count > 0 and frame_index + 1 >= source_frame_count:
                    logger.success("Finished processing the final source frame")
                    break

                frame_index += 1

    asyncio.run(_run())
    return replay_video(input_video, output_log, output_video=output_replay, display=display)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Obstacle-challenge source video processor.")
    parser.add_argument("input_video", type=Path, help="Source video to process.")
    parser.add_argument("--output-log", type=Path, help="Output pickle log path.")
    parser.add_argument("--output-replay", type=Path, help="Annotated replay output path.")
    parser.add_argument("--display", action="store_true", help="Display the replay while rendering it.")
    args = parser.parse_args()

    output_log, output_replay = default_output_paths(args.input_video)
    if args.output_log is not None:
        output_log = args.output_log
    if args.output_replay is not None:
        output_replay = args.output_replay

    logger.info(f"Processing {args.input_video} -> {output_log} and {output_replay}")
    process_video(args.input_video, output_log, output_replay, display=bool(args.display))