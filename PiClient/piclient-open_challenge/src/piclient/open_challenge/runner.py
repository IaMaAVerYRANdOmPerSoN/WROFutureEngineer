"""Open Challenge runner.

Sets up shared memory, camera and vision subprocesses, then runs the
main control loop for the WRO open challenge course.
"""

from typing import Literal

import cv2
import time
import multiprocessing as mp
import numpy as np
from multiprocessing import shared_memory

from loguru import logger

from piclient.core.interface import AsyncCamera
from piclient.core.interface import Client, DriveCommandExecutor
from piclient.core.lib import GLOBAL_CONFIG, PD, export
from piclient.core.vision import OpenChallengeAsyncMultiprocessingVisionProcessor


@export
@logger.contextualize(process="MAIN")
async def run_open_challenge() -> None:
    """Run the live Open Challenge control loop.

    Creates the camera shared-memory block and camera/vision processes, opens
    the Arduino client and drive executor, and submits wall-following commands
    until the configured lap sequence completes. Processes and shared memory
    are cleaned up in the runner's finalization path.

    :returns: ``None`` after completion or a failed connection check.
    :rtype: None
    """

    wall_follow = PD(
        *GLOBAL_CONFIG().OpenChallengeConfig.WALL_FOLLOW_KPKD)
    corner_turn = PD(
        *GLOBAL_CONFIG().OpenChallengeConfig.CORNER_TURN_KPKD)

    # Counter for number of frames where a turn is suspected when in the stratight state, vice versa for the turn state
    hysteresis_counter = 0
    turn_counter = 0
    start_time = None  # Start time for the final straight
    last_turn_time = 0  # Time of the last detected turn

    fps_start_time = time.perf_counter()
    frame_count = 0  # Frame counter (resets every second)
    fps = 0

    state: Literal["Straight", "Turn",
                   "Final Turn", "Final Straight"] = "Straight"

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
            target=OpenChallengeAsyncMultiprocessingVisionProcessor.vision_process_context_manager,
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

            await client.drive_motors(0, 90, 0.1)  # Turn straight

            try:
                async with DriveCommandExecutor(client) as drive:
                    async for walls in OpenChallengeAsyncMultiprocessingVisionProcessor.async_pipe_reader(data_receiver):

                        frame_count += 1
                        now = time.perf_counter()
                        if now - fps_start_time >= 1.0:
                            fps = frame_count / (now - fps_start_time)
                            frame_count = 0
                            fps_start_time = now

                        turn_correction = wall_follow.tick(
                            walls.right - walls.left)
                        corner_turn_correction = corner_turn.tick(
                            walls.right - walls.left)
                        is_turn_detected = walls.center > GLOBAL_CONFIG(
                        ).SharedChallengeConfig.CENTER_FILL_THRESHOLD

                        match state:
                            case "Straight":
                                if (
                                    is_turn_detected
                                    and time.perf_counter() - last_turn_time >= GLOBAL_CONFIG().SharedChallengeConfig.TURN_COOLDOWN
                                ):
                                    hysteresis_counter += 1
                                    if hysteresis_counter >= GLOBAL_CONFIG().SharedChallengeConfig.HYSTERESIS:
                                        turn_counter += 1
                                        last_turn_time: float = time.perf_counter()
                                        state = "Final Turn" if turn_counter >= GLOBAL_CONFIG(
                                        ).SharedChallengeConfig.LAP_LENGTH_IN_TURNS else "Turn"
                                        hysteresis_counter = 0
                                else:
                                    hysteresis_counter = 0

                                drive.submit(
                                    GLOBAL_CONFIG().OpenChallengeConfig.STRAIGHT_SPEED,
                                    turn_correction * 90 + 90,
                                    GLOBAL_CONFIG().SharedChallengeConfig.DRIVE_COMMAND_DURATION,
                                )

                            case "Turn": # pyright: ignore[reportUnnecessaryComparison]
                                if not is_turn_detected:
                                    hysteresis_counter += 1
                                    if hysteresis_counter >= GLOBAL_CONFIG().SharedChallengeConfig.HYSTERESIS:
                                        state = "Straight"
                                        hysteresis_counter = 0
                                else:
                                    hysteresis_counter = 0

                                drive.submit(
                                    GLOBAL_CONFIG().OpenChallengeConfig.TURN_SPEED,
                                    corner_turn_correction * 90 + 90,
                                    GLOBAL_CONFIG().SharedChallengeConfig.DRIVE_COMMAND_DURATION,
                                )

                            case "Final Turn": # pyright: ignore[reportUnnecessaryComparison]
                                if not is_turn_detected:
                                    hysteresis_counter += 1
                                    if hysteresis_counter >= GLOBAL_CONFIG().SharedChallengeConfig.HYSTERESIS:
                                        state = "Final Straight"
                                        hysteresis_counter = 0
                                else:
                                    hysteresis_counter = 0

                                drive.submit(
                                    GLOBAL_CONFIG().OpenChallengeConfig.TURN_SPEED,
                                    corner_turn_correction * 90 + 90,
                                    GLOBAL_CONFIG().SharedChallengeConfig.DRIVE_COMMAND_DURATION,
                                )

                            case "Final Straight":
                                start_time = time.perf_counter() if not start_time else start_time
                                now = time.perf_counter()

                                if now - start_time > 2.0:
                                    logger.success("Finished!")
                                    break

                                drive.submit(
                                    GLOBAL_CONFIG().OpenChallengeConfig.STRAIGHT_SPEED,
                                    turn_correction * 90 + 90,
                                    GLOBAL_CONFIG().SharedChallengeConfig.DRIVE_COMMAND_DURATION,
                                )

                            case _:
                                logger.error(f"Unrecognized state: {state}")
                                state = "Straight"

                        h, w, c = GLOBAL_CONFIG().CameraConfig.OUTPUT_SHAPE
                        debug_frame = np.ndarray(
                            (h, w, c), dtype=np.uint8, buffer=shm.buf)

                        cv2.line(debug_frame, (w // 2, h), (int(w / 2 - turn_correction *
                                 # Draws the turning vector
                                                                w / 2), h - 50), (0, 255, 0), 2)
                        cv2.putText(debug_frame, f"State: {state} | Turns: {turn_counter} | FPS: {fps:.1f} | PD: {(turn_correction if state == 'Straight' or state == 'Final Straight' else corner_turn_correction):.3f}", (
                            # Info on the top
                            5, 10), cv2.FONT_HERSHEY_PLAIN, 0.6, (255, 255, 255), 1)

                        l_roi = GLOBAL_CONFIG().VisionConfig.LEFT_WALL_ROI
                        r_roi = GLOBAL_CONFIG().VisionConfig.RIGHT_WALL_ROI
                        c_roi = GLOBAL_CONFIG().VisionConfig.CENTER_WALL_ROI

                        cv2.rectangle(  # Draws left ROI
                            debug_frame,
                            (0, l_roi[0].start),
                            (l_roi[1].stop, l_roi[0].stop),
                            (255, 0, 0), 2
                        )
                        cv2.rectangle(  # Draws right ROI
                            debug_frame,
                            (r_roi[1].start, r_roi[0].start),
                            (w, r_roi[0].stop),
                            (0, 0, 255), 2
                        )
                        cv2.rectangle(  # Draws center ROI
                            debug_frame,
                            (c_roi[1].start, c_roi[0].start),
                            (c_roi[1].stop, c_roi[0].stop),
                            (0, 255, 0), 2
                        )

                        cv2.imshow("Debug", debug_frame)
                        cv2.waitKey(1)  # Shows frame for 1 ms
            finally:
                await client.drive_motors(0, 90, 0.1)  # Stops robot

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
