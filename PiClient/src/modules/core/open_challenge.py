"""Open Challenge runner.

Sets up shared memory, camera and vision subprocesses, then runs the
main control loop for the WRO open challenge course.
"""

import multiprocessing as mp
from multiprocessing import shared_memory
from src.modules.interface.async_camera import AsyncCamera
from src.modules.vision.async_open import OpenChallengeAsyncMultiprocessingVisionProcessor
import numpy as np
import cv2
from src.modules.interface.comm_protocol import Client, DriveCommandExecutor
from src.modules.lib.config import Config
from src.modules.lib.controller import PD
from src import logger
import time
from typing import Literal

async def run_open_challenge():
    """
    asynchronus runner for the *open challenge*
    """

    wall_follow = PD(*Config.OpenChallengeConfig.WALL_FOLLOW_KPKD)
    corner_turn = PD(*Config.OpenChallengeConfig.CORNER_TURN_KPKD)
    
    hysteresis_counter = 0 # Counter for number of frames where a turn is suspected when in the stratight state, vice versa for the turn state
    initial_turn_sign = 0 # Direction of the turn
    turn_counter = 0
    start_time = None # Start time for the final straight

    fps_start_time = time.perf_counter()
    frame_count = 0 # Frame counter (resets every second)
    fps = 0
    
    state: Literal["Straight", "Turn", "Final Turn", "Final Straight"] = "Straight"

    # Create the shared memory block and spawn processes
    try: 
        try:
            shm = shared_memory.SharedMemory(
                create=True, size=512*384*3, name="camera_frame")
        except FileExistsError:
            try:
                shm = shared_memory.SharedMemory(name="camera_frame")
                shm.close()
                shm.unlink()
                # Make sure it has exactly the size we need, and is empty
                shm = shared_memory.SharedMemory(
                    create=True, size=512*384*3, name="camera_frame")
            except FileNotFoundError:
                # The shared memory segment disappeared between create and cleanup attempts, try again
                shm = shared_memory.SharedMemory(
                    create=True, size=512*384*3, name="camera_frame")

        cam_receiver, cam_sender = mp.Pipe(duplex=False)
        camera_process = mp.Process(
            target=AsyncCamera.camera_process_context_manager, args=(shm.name, cam_sender,))
        camera_process.start()

        data_receiver, data_sender = mp.Pipe(duplex=False)
        vision_process = mp.Process(target=OpenChallengeAsyncMultiprocessingVisionProcessor.vision_process_context_manager, args=(
            shm.name, cam_receiver, data_sender,))
        vision_process.start()

        # Camera process dumps frames into shared memory, and sends a signal through cam_sender when a new frame is ready.
        # Vision process listens on cam_receiver for the signal, then reads the frame from shared memory, processes it, and sends the results back through data_sender.
        # Staticmethod async_pipe_reader polls the data_receiver for data and yields it to the main loop.
    
        async with Client() as client: # Initilize the client and open resources with the async context manager
            if not await client.verify_connection():
                logger.critical(
                    f"Couldn't establish connection to Arduino, is the USB cable plugged in? The selected USB port is {client.PORT}, baud {client.BAUD} (check config.py).")
                return

            await client.drive_motors(0, 0, 0.1) # Turn straight

            try:
                async with DriveCommandExecutor(client) as drive:
                    async for walls in OpenChallengeAsyncMultiprocessingVisionProcessor.async_pipe_reader(data_receiver):

                        frame_count += 1
                        now = time.perf_counter()
                        if now - fps_start_time >= 1.0:
                            fps = frame_count / (now - fps_start_time)
                            frame_count = 0
                            fps_start_time = now

                        turn_correction = wall_follow.tick(walls.right - walls.left)
                        corner_turn_correction = corner_turn.tick(walls.right - walls.left)
                        is_turn_detected = abs(turn_correction) > Config.OpenChallengeConfig.TURN_DETECTION_THRESHOLD

                        match state:
                            case "Straight":
                                if is_turn_detected:
                                    current_turn_sign = np.sign(turn_correction)
                                    if hysteresis_counter == 0:
                                        # Start of potential turn, lock the direction
                                        initial_turn_sign = current_turn_sign
                                        hysteresis_counter = 1
                                    elif current_turn_sign == initial_turn_sign:
                                        # Direction matches, increment confidence
                                        hysteresis_counter += 1
                                    else:
                                        # Sign flipped! Reset and start counting for the new direction
                                        initial_turn_sign = current_turn_sign
                                        hysteresis_counter = 1

                                    if hysteresis_counter >= Config.OpenChallengeConfig.TURN_HYSTERESIS:
                                        turn_counter += 1
                                        if turn_counter >= Config.OpenChallengeConfig.LAP_LENGTH_IN_TURNS:
                                            state = "Final Turn"
                                        else:
                                            state = "Turn"
                                        hysteresis_counter = 0
                                        # initial_turn_sign is preserved to validate the turn duration
                                else:
                                    hysteresis_counter = 0
                                    initial_turn_sign = 0 # Reset initial sign

                                drive.submit(
                                    Config.OpenChallengeConfig.STRAIGHT_SPEED,
                                    turn_correction * 90 + 90,
                                    Config.OpenChallengeConfig.DRIVE_COMMAND_DURATION,
                                )

                            case "Turn":
                                is_still_our_turn = is_turn_detected and np.sign(turn_correction) == initial_turn_sign

                                if not is_still_our_turn:
                                    hysteresis_counter += 1
                                    if hysteresis_counter >= Config.OpenChallengeConfig.TURN_HYSTERESIS:
                                        state = "Straight"
                                        hysteresis_counter = 0
                                        initial_turn_sign = 0
                                else:
                                    hysteresis_counter = 0

                                drive.submit(
                                    Config.OpenChallengeConfig.TURN_SPEED,
                                    corner_turn_correction * 90 + 90,
                                    Config.OpenChallengeConfig.DRIVE_COMMAND_DURATION,
                                )

                            case "Final Turn":
                                is_still_our_turn = is_turn_detected and np.sign(turn_correction) == initial_turn_sign

                                if not is_still_our_turn:
                                    hysteresis_counter += 1
                                    if hysteresis_counter >= Config.OpenChallengeConfig.TURN_HYSTERESIS:
                                        state = "Final Straight"
                                        hysteresis_counter = 0
                                        initial_turn_sign = 0
                                else:
                                    hysteresis_counter = 0

                                drive.submit(
                                    Config.OpenChallengeConfig.TURN_SPEED,
                                    corner_turn_correction * 90 + 90,
                                    Config.OpenChallengeConfig.DRIVE_COMMAND_DURATION,
                                )

                            case "Final Straight":
                                start_time = time.perf_counter() if not start_time else start_time
                                now = time.perf_counter()

                                if now - start_time > 0.5:
                                    logger.success("Finished!")
                                    break

                                drive.submit(
                                    Config.OpenChallengeConfig.STRAIGHT_SPEED,
                                    turn_correction * 90 + 90,
                                    Config.OpenChallengeConfig.DRIVE_COMMAND_DURATION,
                                )

                            case _:
                                logger.error(f"Unrecogized state: {state}")
                                state = "Straight"

                        h, w = Config.CameraConfig.OUTPUT_HEIGHT, Config.CameraConfig.OUTPUT_WIDTH 
                        c = Config.CameraConfig.OUTPUT_CHANNELS
                        debug_frame = np.ndarray((h, w, c), dtype=np.uint8, buffer=shm.buf)[Config.VisionConfig.INITIAL_ROI]  # Get the frame from shared memory
                        h, w, c = debug_frame.shape

                        cv2.line(debug_frame, (w // 2, h), (int(w / 2 - turn_correction * w / 2), h - 50), (0, 255, 0), 2) # Draws the turning vector
                        cv2.putText(debug_frame, f"Turns: {turn_counter} | FPS: {fps:.1f} | PD: {(turn_correction if state == 'Straight' or state == 'Final Straight' else corner_turn_correction):.3f}", (5, 10), cv2.FONT_HERSHEY_PLAIN, 0.6, (255, 255, 255), 1) # Info on the top

                        l_roi = Config.VisionConfig.LEFT_WALL_ROI
                        r_roi = Config.VisionConfig.RIGHT_WALL_ROI

                        cv2.rectangle( # Draws left ROI
                            debug_frame,
                            (0, l_roi[0].start),
                            (l_roi[1].stop, l_roi[0].stop),
                            (255, 0, 0), 2
                        )
                        cv2.rectangle( # Draws right ROI
                            debug_frame,
                            (r_roi[1].start, r_roi[0].start),
                            (512, r_roi[0].stop),
                            (0, 0, 255), 2
                        )

                        cv2.imshow("Debug", debug_frame)
                        cv2.waitKey(1) # Shows frame for 1 ms
            finally:
                await client.drive_motors(0, 0, 0.1) # Stops robot

    finally: # Cleans up everything
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
            
            logger.info("Exited cleanly")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            logger.warning(
                f"Leaked memory segments and processes may need to be cleaned up manually. Good luck finding them michael -_-")
