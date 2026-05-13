import asyncio
from typing import Literal
from src import logger
from src.modules.async_camera import AsyncCamera
from src.modules.comm_protocol import Client
from src.modules.vision_processing import OpenChallengeAsyncMultiprocessingVisionProcessor, VisionObject
from src.modules.controller import PD
from src.modules.config import Config
import multiprocessing as mp
from multiprocessing import shared_memory
from numpy import isinf


async def run_open_challenge():
    async with Client() as client:
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
                target=AsyncCamera.camera_process_context_manager, args=(shm.name, cam_sender,))
            camera_process.start()

            data_receiver, data_sender = mp.Pipe(duplex=False)
            vision_process = mp.Process(target=OpenChallengeAsyncMultiprocessingVisionProcessor.vision_process_context_manager, args=(
                shm.name, cam_receiver, data_sender,))
            vision_process.start()

            # Camera process dumps frames into shared memory, and sends a signal through cam_sender when a new frame is ready.
            # Vision process polls cam_receiver and sends results through data_sender.
            # Saticmethod data_yielder polls the data_receiver for data and yields it to to the main loop.

            # pyright: ignore[reportArgumentType]
            async for zone, walls, corner_lines, wall_x_diffs in OpenChallengeAsyncMultiprocessingVisionProcessor.async_pipe_reader(data_receiver):

                assert isinstance(zone, VisionObject) or zone is None
                assert isinstance(walls, tuple) and all(
                    isinstance(wall, VisionObject) for wall in walls)
                assert isinstance(corner_lines, tuple) and all(isinstance(
                    line, VisionObject) for line in corner_lines) or not corner_lines  # Empty tuple is fine

                logger.debug(
                    f"Zone: {zone}, Walls: {walls}, Corner Lines: {corner_lines}, Wall Dists: {wall_x_diffs}")
                state_history[1] = (state_history[1] +
                                    1 if state_history[0] == state else 0)

                if state_history[0] == "Turn" and state != "Turn" and state_history[1] > Config.OpenChallengeConfig.TURN_HYSTERESIS:
                    turn_counter += 1
                    if turn_counter > Config.OpenChallengeConfig.LAP_LENGTH_IN_TURNS:
                        # TODO: Call function that ends the run loop and does the parallel parking maneuver, then break
                        break

                # Change state tracker after checking for turn
                state_history[0] = state

                match state:
                    case "Follow wall":
                        if any(isinf(x_diff) for x_diff in wall_x_diffs.values()):
                            corner_turn_controller.previous_error = 0
                            state = "Turn"

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
                        if state_history[1] > Config.OpenChallengeConfig.TURN_HYSTERESIS and corner_lines:
                            if corner_lines[0].color == "blue":  # Left turn
                                await client.drive_motors(
                                    Config.OpenChallengeConfig.TURN_SPEED,
                                    - Config.OpenChallengeConfig.TURN_ANGLE,
                                    Config.OpenChallengeConfig.TURN_DURATION,
                                )
                            # Right turn, pyright do you not see the assertion on line 70 that guarantees corner_lines contains VisionObjects, or is just an empty tuple that skips this block entirely?
                            elif corner_lines[0].color == "orange":
                                await client.drive_motors(
                                    Config.OpenChallengeConfig.TURN_SPEED,
                                    Config.OpenChallengeConfig.TURN_ANGLE,
                                    Config.OpenChallengeConfig.TURN_DURATION,
                                )
                            # await blocks so we can be sure the turn is done before switching states
                            state = "Follow wall"

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
