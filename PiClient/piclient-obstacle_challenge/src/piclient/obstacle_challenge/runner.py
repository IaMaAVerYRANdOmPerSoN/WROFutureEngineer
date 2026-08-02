"""
Runner for the obstacle challenge.
"""

import cv2
import numpy as np
from functools import partial
from pathlib import Path
from time import time
from loguru import logger

from piclient.core.interface import AsyncCamera, DriveCommandExecutor, Client, Recorder
from piclient.core.lib import ProcessContextManager, GLOBAL_CONFIG, export
from piclient.core.vision import ObstacleChallengeAsyncMultiprocessingVisionProcessor, WallsAndObstacles

from .obstacle_challenge import ObstacleChallengeStateMachine
from .video_tools import DriveCommand, PickleLogWriter, build_log_record, default_output_paths, replay_video
from .transition_determinants import (
    TypedTranisitionManager,
    should_avoid_obstacle,
    should_straight,
    should_turn,
    should_final_turn,
    should_final_straight
)


@export
@logger.contextualize(process="MAIN")
async def run_obstacle_challenge() -> None:
    run_started_at = int(time())
    log_path, replay_path = default_output_paths(Path(f"WRO_recordings/recording_{run_started_at}.mp4"))
    recording_path = log_path.with_suffix(".mp4")
    recorder_callback = partial(Recorder.recorder_process_context_manager)
    process_manager = ProcessContextManager(
        camera_callback=AsyncCamera.camera_process_context_manager,
        vision_callback=ObstacleChallengeAsyncMultiprocessingVisionProcessor.vision_process_context_manager,
        recorder_callback=recorder_callback,
    )

    replay_generated = False
    try:
        async with Client() as client:
            drive_executor = DriveCommandExecutor(client=client)
            async with ObstacleChallengeStateMachine(
                initial_state="straight",
                drive_command_executor=drive_executor,
                transition_manager=TypedTranisitionManager(
                    hysteresis_values=[GLOBAL_CONFIG().SharedChallengeConfig.HYSTERESIS] * 5,
                    priorities=[5, 3, 4, 2, 1],
                    obstacle_avoidance=should_avoid_obstacle,
                    straight=should_straight,
                    turn=should_turn,
                    final_turn=should_final_turn,
                    final_straight=should_final_straight,
                ),
            ) as state_machine:
                with PickleLogWriter(log_path) as log_writer:
                    with process_manager as process_context:
                        if process_context.output_stream is None:
                            raise RuntimeError("Output stream is not initialized.")

                        frame_index = 0
                        source_fps = GLOBAL_CONFIG().CameraConfig.FPS
                        shm = process_context.shm
                        frame_buffer = shm.buf if shm is not None else None
                        h = GLOBAL_CONFIG().CameraConfig.OUTPUT_HEIGHT
                        w = GLOBAL_CONFIG().CameraConfig.OUTPUT_WIDTH
                        c = GLOBAL_CONFIG().CameraConfig.OUTPUT_CHANNELS

                        async for data in ObstacleChallengeAsyncMultiprocessingVisionProcessor.async_pipe_reader(process_context.output_stream):
                            walls_and_obstacles: WallsAndObstacles = data[0]
                            target: tuple[int, int] | None = data[1]

                            state_machine.update(walls_and_obstacles, target)
                            finished = state_machine.handle_state_actions()

                            log_writer.write(
                                build_log_record(
                                    frame_index=frame_index,
                                    timestamp_s=frame_index / source_fps,
                                    state=state_machine.current_state,
                                    turn_counter=state_machine.turn_counter,
                                    last_turn_time_s=state_machine.last_turn_time,
                                    start_time_s=state_machine.start_time,
                                    target=state_machine.target_position,
                                    walls_and_obstacles=state_machine.walls_and_obstacles,
                                    wall_error=state_machine.wall_error,
                                    turn_correction=state_machine.turn_correction,
                                    corner_turn_correction=state_machine.corner_turn_correction,
                                    obstacle_avoidance_correction=state_machine.obstacle_avoidance_correction,
                                    command=DriveCommand(*drive_executor.latest_command),
                                    command_submitted=drive_executor.command_submitted,
                                    finished=finished,
                                )
                            )
                            drive_executor.command_submitted = False

                            debug_frame = np.ndarray((h, w, c), dtype=np.uint8, buffer=frame_buffer)
                            if walls_and_obstacles.walls.left_raw is not None and walls_and_obstacles.walls.right_raw is not None:
                                cv2.drawContours(debug_frame, [walls_and_obstacles.walls.left_raw.contour, walls_and_obstacles.walls.right_raw.contour], -1, (0, 255, 0), 2)
                            if target is not None:
                                cv2.circle(debug_frame, (*target,), 5, (0, 0, 255), -1)
                            cv2.putText(debug_frame, f"FPS: {state_machine.fps:.2f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
                            cv2.putText(debug_frame, f"State: {state_machine.current_state}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)

                            cv2.imshow("Obstacle Challenge Debug", debug_frame)
                            if cv2.waitKey(1) & 0xFF == ord('q'):
                                break

                            if finished:
                                break

                            frame_index += 1

        replay_video(recording_path, log_path, output_video=replay_path, display=False)
        replay_generated = True
    finally:
        if not replay_generated and log_path.exists() and recording_path.exists():
            try:
                replay_video(recording_path, log_path, output_video=replay_path, display=False)
            except Exception:
                logger.exception("Failed to generate obstacle-challenge replay")