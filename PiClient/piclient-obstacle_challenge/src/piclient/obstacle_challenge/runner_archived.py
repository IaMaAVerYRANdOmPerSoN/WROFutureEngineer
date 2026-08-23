"""Obstacle Challenge runner.

Sets up shared memory, camera and vision subprocesses, then runs the
main control loop for the WRO obstacle challenge course.
"""

import time
import multiprocessing as mp
from multiprocessing import shared_memory

import cv2
import numpy as np

from loguru import logger
from piclient.core.interface import AsyncCamera, Client, DriveCommandExecutor
from piclient.core.lib import GLOBAL_CONFIG, PD, export
from piclient.core.vision import (
    ObstacleChallengeAsyncMultiprocessingVisionProcessor,
    WallsAndObstacles,
)

from .transition_determinants import (
    is_straight,
    should_final_turn,
    should_final_straight_and_parking,
    should_straight,
    should_turn,
    should_avoid_obstacle,
    ChallengeState,
    TypedTranisitionManager,
)


manager = TypedTranisitionManager(
    hysteresis_values=[GLOBAL_CONFIG().SharedChallengeConfig.HYSTERESIS] * 5,
    priorities=[2, 1, 3, 4, 0],
    obstacle_avoidance=should_avoid_obstacle,
    straight=should_straight,
    turn=should_turn,
    final_turn=should_final_turn,
    final_straight_and_parking=should_final_straight_and_parking,
)


def get_wall_error(walls_and_obstacles: WallsAndObstacles) -> float:
    """Return the wall-following error as a finite scalar."""
    left_distance = float(walls_and_obstacles.walls.left)
    right_distance = float(walls_and_obstacles.walls.right)

    if not np.isfinite(left_distance) or not np.isfinite(right_distance):
        return 0.0

    return right_distance - left_distance


@export
@logger.catch(reraise=True)
async def run_obstacle_challenge() -> None:
    """
    asynchronous runner for the *obstacle challenge*
    """

    wall_follow = PD(
        *GLOBAL_CONFIG().ObstacleChallengeConfig.WALL_FOLLOW_KPKD)
    corner_turn = PD(
        *GLOBAL_CONFIG().ObstacleChallengeConfig.CORNER_TURN_KPKD)
    obstacle_avoid = PD(
        *GLOBAL_CONFIG().ObstacleChallengeConfig.OBSTACLE_AVOID_KPKD)

    turn_counter = 0
    start_time = None  # Start time for the final straight
    last_turn_time = 0  # Time of the last detected turn

    fps_start_time = time.perf_counter()
    frame_count = 0  # Frame counter (resets every second)
    fps = 0

    state: ChallengeState = "straight"

    # Create the shared memory block and spawn processes
    shm = None
    camera_process = None
    vision_process = None

    try:
        try:
            shm = shared_memory.SharedMemory(
                create=True, size=GLOBAL_CONFIG().CameraConfig.SHM_SIZE, name="camera_frame")
        except FileExistsError:
            try:
                shm = shared_memory.SharedMemory(name="camera_frame")
                shm.close()
                shm.unlink()
                # Make sure it has exactly the size we need, and is empty
                shm = shared_memory.SharedMemory(
                    create=True, size=GLOBAL_CONFIG().CameraConfig.SHM_SIZE, name="camera_frame")
            except FileNotFoundError:
                # The shared memory segment disappeared between create and cleanup attempts, try again
                shm = shared_memory.SharedMemory(
                    create=True, size=GLOBAL_CONFIG().CameraConfig.SHM_SIZE, name="camera_frame")

        cam_receiver, cam_sender = mp.Pipe(duplex=False)
        camera_process = mp.Process(
            name="Camera",
            target=AsyncCamera.camera_process_context_manager,
            args=(shm.name, cam_sender,)
        )
        camera_process.start()

        data_receiver, data_sender = mp.Pipe(duplex=False)
        vision_process = mp.Process(
            name="Vision",
            target=ObstacleChallengeAsyncMultiprocessingVisionProcessor.vision_process_context_manager,
            args=(
                shm.name,
                cam_receiver,
                data_sender,
            )
        )
        vision_process.start()

        # Camera process dumps frames into shared memory, and sends a signal through cam_sender when a new frame is ready.
        # Vision process listens on cam_receiver for the signal, then reads the frame from shared memory, processes it, and sends the results back through data_sender.
        # Staticmethod async_pipe_reader polls the data_receiver for data and yields it to the main loop.

        async with Client() as client:  # Initialize the client and open resources with the async context manager
            if not await client.verify_connection():
                logger.critical(
                    f"Couldn't establish connection to Arduino, is the USB cable plugged in? The selected USB port is {client.port}, baud {client.baud} (check Config.py).")
                return

            await client.drive_motors(0, 0, 0.1)  # Turn straight

            try:
                async with DriveCommandExecutor(client) as drive:
                    async for data in ObstacleChallengeAsyncMultiprocessingVisionProcessor.async_pipe_reader(data_receiver):
                        walls_and_obstacles: WallsAndObstacles = data[0]
                        target: tuple[int, int] | None = data[1]

                        frame_count += 1
                        now = time.perf_counter()
                        if now - fps_start_time >= 1.0:
                            fps = frame_count / (now - fps_start_time)
                            frame_count = 0
                            fps_start_time = now

                        wall_error = get_wall_error(walls_and_obstacles)

                        turn_correction = wall_follow.tick(wall_error)
                        corner_turn_correction = corner_turn.tick(wall_error)

                        is_turn_detected = not is_straight(walls_and_obstacles)

                        if (
                            is_turn_detected
                            and time.perf_counter() - last_turn_time >= GLOBAL_CONFIG().SharedChallengeConfig.TURN_COOLDOWN
                        ):
                            turn_counter += 1
                            last_turn_time = time.perf_counter()

                        next_state: ChallengeState | None = manager.check_transitions(
                            walls_and_obstacles,
                            state,
                            target,
                            last_turn_time,
                            turn_counter,
                            start_time,
                        )
                        if next_state is not None:
                            state = next_state

                        if state == "final_straight_and_parking" and start_time is None:
                            start_time = time.perf_counter()

                        match state:
                            case "obstacle_avoidance":
                                if target is None:  # 1st priority is to avoid obstacles
                                    continue  # Since target is None, we don't want to send a drive command, so we continue to the next iteration of the loop

                                drive.submit(
                                    GLOBAL_CONFIG().ObstacleChallengeConfig.OBSTACLE_AVOID_SPEED,
                                    obstacle_avoid.tick(
                                        0, target[0]) * 90 + 90,
                                    GLOBAL_CONFIG().SharedChallengeConfig.DRIVE_COMMAND_DURATION
                                )

                            case "straight":
                                drive.submit(
                                    GLOBAL_CONFIG().ObstacleChallengeConfig.STRAIGHT_SPEED,
                                    turn_correction * 90 + 90,
                                    GLOBAL_CONFIG().SharedChallengeConfig.DRIVE_COMMAND_DURATION
                                )

                            case "turn":
                                drive.submit(
                                    GLOBAL_CONFIG().ObstacleChallengeConfig.TURN_SPEED,
                                    corner_turn_correction * 90 + 90,
                                    GLOBAL_CONFIG().SharedChallengeConfig.DRIVE_COMMAND_DURATION,
                                )

                            case "final_turn":
                                drive.submit(
                                    GLOBAL_CONFIG().ObstacleChallengeConfig.TURN_SPEED,
                                    corner_turn_correction * 90 + 90,
                                    GLOBAL_CONFIG().SharedChallengeConfig.DRIVE_COMMAND_DURATION,
                                )

                            case "final_straight_and_parking":
                                start_time = time.perf_counter() if not start_time else start_time
                                now = time.perf_counter()

                                if now - start_time > 0.5:
                                    logger.success("Finished!")
                                    break

                                drive.submit(
                                    GLOBAL_CONFIG().ObstacleChallengeConfig.STRAIGHT_SPEED,
                                    turn_correction * 90 + 90,
                                    GLOBAL_CONFIG().SharedChallengeConfig.DRIVE_COMMAND_DURATION,
                                )

                            case _:
                                logger.error(f"Unrecognized state: {state}")
                                state = "straight"  # Reset to a safe state

                        h, w, c = GLOBAL_CONFIG().CameraConfig.OUTPUT_SHAPE
                        debug_frame = np.ndarray((h, w, c), dtype=np.uint8, buffer=shm.buf)

                        cv2.line(debug_frame, (w // 2, h), (int(w / 2 - turn_correction *
                                 # Draws the turning vector
                                                                w / 2), h - 50), (0, 255, 0), 2)
                        cv2.putText(debug_frame, f"State: {state} | Turns: {turn_counter} | FPS: {fps:.1f} | PD: {(turn_correction if state == 'straight' or state == 'final_straight_and_parking' else corner_turn_correction):.3f}", (
                            # Info on the top
                            5, 10), cv2.FONT_HERSHEY_PLAIN, 0.6, (255, 255, 255), 1)

                        c_roi = GLOBAL_CONFIG().VisionConfig.CENTER_WALL_ROI

                        cv2.rectangle(  # Draws center ROI
                            debug_frame,
                            (c_roi[1].start, c_roi[0].start),
                            (c_roi[1].stop, c_roi[0].stop),
                            (0, 255, 0), 2
                        )

                        if walls_and_obstacles.obstacles is not None:
                            for vision_object in walls_and_obstacles.obstacles:
                                # Draws obstacles in yellow
                                cv2.drawContours(
                                    debug_frame, [vision_object.contour], -1, (0, 255, 255), 2)

                        for wall in [walls_and_obstacles.walls.left_raw, walls_and_obstacles.walls.right_raw]:
                            if wall is None or wall.contour.size == 0:
                                continue
                            # Draws walls in cyan
                            cv2.drawContours(
                                debug_frame, [wall.contour], -1, (255, 255, 0), 2)

                        cv2.circle(debug_frame, (target[0], target[1]), 5, (
                            0, 0, 255), -1) if target is not None else None  # Draws target in red

                        cv2.imshow("Debug", debug_frame)
                        cv2.waitKey(1)  # Shows frame for 1 ms
            finally:
                await client.drive_motors(0, 0, 0.1)  # Stops robot

    finally:  # Cleans up everything
        logger.info("Stopping Robot..")

        logger.info("Terminating processes and cleaning up shared memory...")
        try:
            if camera_process and camera_process.is_alive():
                camera_process.terminate()
                camera_process.join(timeout=1)

            if vision_process and vision_process.is_alive():
                vision_process.terminate()
                vision_process.join(timeout=1)

            if shm:
                shm.close()
                shm.unlink()

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            logger.warning(
                f"Leaked memory segments and processes may need to be cleaned up manually. Good luck finding them michael -_-")
