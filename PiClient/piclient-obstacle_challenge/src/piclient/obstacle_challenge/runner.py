"""
Runner for the obstacle challenge.
"""

from functools import partial
from pathlib import Path
from time import time
import traceback
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
    should_parallel_park
)
from .parallel_parking import ParallelParkingStateMachine


def _try_generate_replay(
    recording_path: Path,
    log_path: Path,
    replay_path: Path,
) -> bool:
    """Generate a replay when the recorder produced a usable source file."""
    if not recording_path.is_file() or recording_path.stat().st_size == 0:
        logger.warning(
            f"Skipping obstacle-challenge replay: recording is missing or empty: {recording_path}"
        )
        return False
    if not log_path.is_file() or log_path.stat().st_size == 0:
        logger.warning(
            f"Skipping obstacle-challenge replay: telemetry log is missing or empty: {log_path}"
        )
        return False

    try:
        replay_video(recording_path, log_path, output_video=replay_path, display=False)
    except Exception:
        logger.exception(f"Obstacle-challenge replay generation failed for {recording_path}")
        return False
    return True


@export
@logger.contextualize(process="MAIN")
async def run_obstacle_challenge() -> None:
    """Run the live obstacle challenge and generate a replay recording.

    The runner connects the camera, vision processor, drive executor, state
    machine, recorder, and telemetry logger. After processing ends it renders
    the collected telemetry over the recorded camera video.

    :returns: ``None`` after the run and replay generation finish.
    :rtype: None
    :raises RuntimeError: If a required process output stream is unavailable.
    """
    run_started_at = int(time())
    recording_path = Path(f"WRO_recordings/recording_{run_started_at}.mp4")
    log_path, replay_path = default_output_paths(recording_path)
    recorder_callback = partial(Recorder.recorder_process_context_manager)
    process_manager = ProcessContextManager(
        camera_callback=AsyncCamera.camera_process_context_manager,
        vision_callback=ObstacleChallengeAsyncMultiprocessingVisionProcessor.vision_process_context_manager,
        recorder_callback=recorder_callback,
    )

    replay_generated = False
    try:
        async with Client() as client, DriveCommandExecutor(client=client) as drive_executor, ObstacleChallengeStateMachine(
            initial_state="straight",
            drive_command_executor=drive_executor,
            parallel_parking_state_machine=ParallelParkingStateMachine,
            transition_manager=TypedTranisitionManager(
                hysteresis_values=[GLOBAL_CONFIG().SharedChallengeConfig.HYSTERESIS] * 4,
                priorities=[3, 1, 2, 4],  # parallel_park > obstacle_avoidance > turn > straight
                obstacle_avoidance=should_avoid_obstacle,
                straight=should_straight,
                turn=should_turn,
                parallel_park=should_parallel_park
            ),
        ) as state_machine:
            with PickleLogWriter(log_path) as log_writer, process_manager as process_context:
                if process_context.output_stream is None:
                    raise RuntimeError("Output stream is not initialized.")

                frame_index = 0
                source_fps = GLOBAL_CONFIG().CameraConfig.FPS

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
                            lap_counter=state_machine.lap_counter,
                            last_lap_time=state_machine.last_lap_time,
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

                    if finished:
                        break

                    frame_index += 1

        logger.success("Obstacle challenge completed successfully, generating replay video...")
        replay_generated = _try_generate_replay(recording_path, log_path, replay_path)

    except (KeyboardInterrupt, SystemExit):
        logger.error(
            "Obstacle challenge runner cancelled by user, generating replay video...",
        )
        if not replay_generated:
            _try_generate_replay(recording_path, log_path, replay_path)