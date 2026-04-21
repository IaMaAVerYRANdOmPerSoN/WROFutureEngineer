import asyncio
from typing import Literal
from src import logger
from src.modules.commProtocol import Client
from src.modules.visionProcessing import OpenChallengeAsyncMultiprocessingVisionProcessor, VisionObject
from src.modules.asyncCamera import AsyncCamera
from src.modules.controller import PD
import multiprocessing as mp
from multiprocessing import shared_memory
from multiprocessing.connection import Connection
from src.modules.config import Config
from numpy import isinf


def stream_camera_in_subprocess(camera: AsyncCamera, *args, **kwargs):
    asyncio.run(camera.stream(*args, **kwargs))


def run_analysis_in_subprocess(vision: OpenChallengeAsyncMultiprocessingVisionProcessor, *args, **kwargs):
    asyncio.run(vision.comprehensive_analysis(*args, **kwargs))


async def run_open_challenge():
    async with Client() as client, OpenChallengeAsyncMultiprocessingVisionProcessor() as vision, AsyncCamera() as camera:
        wall_follow = PD(*Config.OpenChallengeConfig.WALL_FOLLOW_KPKD)
        corner_turn_controller = PD(
            *Config.OpenChallengeConfig.CORNER_TURN_KPKD)

        # Runtime checks
        if not await client.verify_connection():
            logger.critical(
                f"Couldn't establish connection to Arduino, is the USB cable plugged in? The selected USB port is {client.PORT}, baud {client.BAUD} (check config.py).")
            return

        # Starting code here
        state: Literal["Follow wall", "Turn", "Hybrid"] = "Follow wall"
        state_history = [state, 0]  # tracks how long we've been in a state
        turn_counter = 0

        camera_process, vision_process, shm = None, None, None

        try:
            # Make sure it has exactly the size we need, and is empty")
            shm = shared_memory.SharedMemory(
                create=True, size=Config.OpenChallengeConfig.SHM_SIZE, name=Config.OpenChallengeConfig.SHM_NAME)
        except FileExistsError:
            try:
                shm = shared_memory.SharedMemory(
                    name=Config.OpenChallengeConfig.SHM_NAME)
                shm.close()
                shm.unlink()
                # Make sure it has exactly the size we need, and is empty
                shm = shared_memory.SharedMemory(
                    create=True, size=Config.OpenChallengeConfig.SHM_SIZE, name=Config.OpenChallengeConfig.SHM_NAME)
            except FileNotFoundError:
                # The shared memory segment disappeared between create and cleanup attempts, try again
                shm = shared_memory.SharedMemory(
                    create=True, size=Config.OpenChallengeConfig.SHM_SIZE, name=Config.OpenChallengeConfig.SHM_NAME)

        try:
            cam_receiver, cam_sender = mp.Pipe(duplex=False)
            camera_process = mp.Process(
                target=stream_camera_in_subprocess, args=(camera, shm.name, cam_sender,))
            camera_process.start()

            data_receiver, data_sender = mp.Pipe(duplex=False)
            vision_process = mp.Process(target=run_analysis_in_subprocess, args=(
                vision, shm.name, cam_receiver, data_sender,))
            vision_process.start()

            # Camera process dumps frames into shared memory, and sends a signal through cam_sender when a new frame is ready.
            # Vision process polls cam_receiver and sends results through data_sender.
            # Saticmethod data_yielder polls the data_receiver for data and yields it to to the main loop.

            async for zone, walls, corner_lines, wall_x_diffs in OpenChallengeAsyncMultiprocessingVisionProcessor.async_pipe_reader(data_receiver):

                assert isinstance(zone, VisionObject) or zone is None
                assert isinstance(walls, tuple) and all(
                    isinstance(wall, VisionObject) for wall in walls)
                assert isinstance(corner_lines, tuple) and all(isinstance(
                    line, VisionObject) for line in corner_lines) or not corner_lines  # Empty tuple

                logger.debug(
                    f"Zone: {zone}, Walls: {walls}, Corner Lines: {corner_lines}, Wall Dists: {wall_x_diffs}")
                state_history[1] = (state_history[1] +
                                    1 if state_history[0] == state else 0)
                state_history[0] = state

                if state_history[0] == "Turn" and state_history[1] > Config.OpenChallengeConfig.TURN_HYSTERESIS and not corner_lines:
                    turn_counter += 1
                    if turn_counter > Config.OpenChallengeConfig.LAP_LENGTH_IN_TURNS:
                        # TODO: Call function that ends the run loop and does the parallel parking maneuver, then break
                        break

                match state:
                    case "Follow wall":
                        if any(isinf(x_diff) for x_diff in wall_x_diffs.values()):
                            corner_turn_controller.previous_error = 0
                            state = "Turn"

                        elif corner_lines:  # We know that that the walls are still good from the previous condition, so we can use hybrid mode
                            corner_turn_controller.previous_error = 0
                            state = "Hybrid"

                        else:
                            turn_correction = wall_follow.tick(
                                wall_x_diffs["left"] - wall_x_diffs["right"])
                            asyncio.create_task(
                                client.drive_motors(
                                    Config.OpenChallengeConfig.STRAIGHT_SPEED,
                                    turn_correction,
                                    Config.OpenChallengeConfig.DRIVE_COMMAND_DURATION,
                                )
                            )  # I really hope my dt is a lot less than 0.1s; this is so it keeps going for a bit
                            # If like something silly happens with the os or some of my other processes
                            # Also add dynamic speed calculation and dynamic dt calculation

                    case "Turn":
                        if not corner_lines:
                            wall_follow.previous_error = 0
                            state = "Follow wall"

                        # We know that the corner lines are still good from the previous condition, so we can use hybrid mode
                        elif not any(isinf(x_diff) for x_diff in wall_x_diffs.values()):
                            wall_follow.previous_error = 0
                            state = "Hybrid"

                        else:
                            turn_correction = corner_turn_controller.tick(
                                # Biggest corner line x - frame center
                                corner_lines[0].x_centroid - Config.CameraConfig.FORMAT["size"][0] // 2)
                            asyncio.create_task(
                                client.drive_motors(
                                    Config.OpenChallengeConfig.TURN_SPEED,
                                    turn_correction,
                                    Config.OpenChallengeConfig.DRIVE_COMMAND_DURATION,
                                )
                            )

                    case "Hybrid":  # Use when both corner lines and wall distance data are good
                        if not corner_lines:
                            wall_follow.previous_error = 0
                            state = "Follow wall"

                        elif any(isinf(x_diff) for x_diff in wall_x_diffs.values()):
                            corner_turn_controller.previous_error = 0
                            state = "Turn"

                        else:
                            turn_correction = (
                                wall_follow.tick(
                                    wall_x_diffs["left"] - wall_x_diffs["right"])
                                + corner_turn_controller.tick(
                                    corner_lines[0].x_centroid
                                    # Biggest corner line x - frame center
                                    - Config.CameraConfig.FORMAT["size"][0] // 2)
                                // 2)  # Average
                            asyncio.create_task(
                                client.drive_motors(
                                    Config.OpenChallengeConfig.HYBRID_SPEED,
                                    turn_correction,
                                    Config.OpenChallengeConfig.DRIVE_COMMAND_DURATION,
                                )
                            )

                    case _:
                        logger.error(f"Invalid state {state}")
                        if not corner_lines and not any(isinf(x_diff) for x_diff in wall_x_diffs.values()):
                            wall_follow.previous_error = 0
                            state = "Follow wall"

                        else:
                            corner_turn_controller.previous_error = 0
                            state = "Turn"
        finally:
            logger.info(
                "Terminating processes and destroying shared memory... ")
            try:
                await client.drive_motors(0, 0, 0)  # Stop the robot
                camera_process.terminate() if camera_process and camera_process.is_alive() else None
                vision_process.terminate() if vision_process and vision_process.is_alive() else None
                camera_process.join(
                    timeout=1) if camera_process and camera_process.is_alive() else None
                vision_process.join(
                    timeout=1) if vision_process and vision_process.is_alive() else None
                shm.close() if shm else None
                shm.unlink() if shm else None
                logger.info("Done")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
                logger.warning(
                    f"Leaked memory segments and processes may need to be cleaned up manually. Good luck finding them michael -_-")
