import asyncio
from typing import Literal
from loguru import logger
from src.commProtocol import Client
from src.visionProcessing import AsyncMultiprocessingVisionProcessor, VisionObject
from src.asyncCamera import AsyncCamera
from src.controller import PD
import multiprocessing as mp
from multiprocessing import shared_memory
from multiprocessing.connection import Connection
from src.config import Config

def stream_camera_in_subprocess(camera: AsyncCamera, *args, **kwargs):
    asyncio.run(camera.stream(*args, **kwargs))

def run_analysis_in_subprocess(vision: AsyncMultiprocessingVisionProcessor, *args, **kwargs):
    asyncio.run(vision.comprehensive_analysis(*args, **kwargs))

async def run():
    async with Client() as client, AsyncMultiprocessingVisionProcessor() as vision, AsyncCamera() as camera:
        wall_follow = PD(*Config.OpenChallengeConfig.WALL_FOLLOW_KPKD)
        corner_turn_controller = PD(*Config.OpenChallengeConfig.CORNER_TURN_KPKD)

        # Starting code here
        state: Literal["Follow wall", "Turn"] = "Follow wall"

        try:
            shm = shared_memory.SharedMemory(create=True, size=Config.OpenChallengeConfig.SHM_SIZE, name=Config.OpenChallengeConfig.SHM_NAME) # Make sure it has exactly the size we need, and is empty")
        except FileExistsError:
            try:
                shm = shared_memory.SharedMemory(name=Config.OpenChallengeConfig.SHM_NAME)
                shm.close()
                shm.unlink()
                shm = shared_memory.SharedMemory(create=True, size=Config.OpenChallengeConfig.SHM_SIZE, name=Config.OpenChallengeConfig.SHM_NAME) # Make sure it has exactly the size we need, and is empty
            except FileNotFoundError:
                # The shared memory segment disappeared between create and cleanup attempts, try again
                shm = shared_memory.SharedMemory(create=True, size=Config.OpenChallengeConfig.SHM_SIZE, name=Config.OpenChallengeConfig.SHM_NAME)


        try:
            cam_receiver, cam_sender = mp.Pipe(duplex = False)
            camera_process = mp.Process(target = stream_camera_in_subprocess, args=(camera, shm.name, cam_sender,))
            camera_process.start()

            data_receiver, data_sender = mp.Pipe(duplex = False)
            vision_process = mp.Process(target = run_analysis_in_subprocess, args=(vision, shm.name, cam_receiver, data_sender,))
            vision_process.start()

            # Camera process dumps frames into shared memory, and sends a signal through cam_sender when a new frame is ready.
            # Vision process polls cam_receiver and sends results through data_sender.
            # Saticmethod data_yielder polls the data_receiver for data and yeilds it to to the main loop.

            async for zone, walls, obstacles, corner_lines, wall_x_diffs, obstacle_dists in AsyncMultiprocessingVisionProcessor.async_pipe_reader(data_receiver):

                assert isinstance(zone, VisionObject) or zone is None
                assert isinstance(walls, tuple) and all(isinstance(wall, VisionObject) for wall in walls)
                assert isinstance(obstacles, tuple) and all(isinstance(obstacle, VisionObject) for obstacle in obstacles)
                assert isinstance(corner_lines, tuple) and all(isinstance(line, VisionObject) for line in corner_lines)

                logger.debug(f"Zone: {zone}, Walls: {walls}, Obstacles: {obstacles}, Corner Lines: {corner_lines}, Wall Dists: {wall_x_diffs}, Obstacle Dists: {obstacle_dists}")

                match state:
                    case "Follow wall":
                        if corner_lines or any(np.isinf(x_diff) for x_diff in wall_x_diffs.values()):
                            corner_turn_controller.previous_error = 0
                            state = "Turn"
                        else:
                            turn_correction = wall_follow.tick(wall_x_diffs["left"] - wall_x_diffs["right"])
                            asyncio.create_task(
                                client.drive_motors(
                                    Config.OpenChallengeConfig.DRIVE_SPEED,
                                    turn_correction,
                                    Config.OpenChallengeConfig.DRIVE_COMMAND_DURATION,
                                )
                            ) # I really hopy my dt is at lot less then 0.1s, this is so it keeps going for a bit
                            # If like something silly happens with the os or some of my other processes
                            # Also add dynamic speed calculation and dynamic dt calculation

                    case "Turn":
                        if not corner_lines:
                            wall_follow.previous_error = 0
                            state = "Follow wall"
                        else:
                            turn_correction = corner_turn_controller.tick(corner_lines[0].x_centroid - Config.CameraConfig.FORMAT["size"][0] // 2) # Biggest corner line x - frame center
                            asyncio.create_task(
                                client.drive_motors(
                                    Config.OpenChallengeConfig.DRIVE_SPEED,
                                    turn_correction,
                                    Config.OpenChallengeConfig.DRIVE_COMMAND_DURATION,
                                )
                            )

                    case _:
                        logger.error(f"Invalid state {state}")
                        state = "Follow wall"
        finally:
            logger.info("Terminating processes and destroying shared memory... ")
            try:
                await client.drive_motors(0, 0, 0) # Stop the robot
                camera_process.terminate() if camera_process.is_alive() else None
                vision_process.terminate() if vision_process.is_alive() else None
                camera_process.join(timeout = 1) if camera_process.is_alive() else None
                vision_process.join(timeout = 1) if vision_process.is_alive() else None
                shm.close()
                shm.unlink()
                logger.info("Done")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
                logger.warning(f"Leaked memory segments and processes may need to be cleaned up manually. Good luck finding them michael -_-")