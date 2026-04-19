import asyncio
import sys
from typing import Literal
from loguru import logger
from src.commProtocol import Client
from src.visionProcessing import AsyncMultiprocessingVisionProcessor, VisionObject
from src.asyncCamera import AsyncCamera
from src.controller import PD
import multiprocessing as mp
from multiprocessing import shared_memory
import cv2
import numpy as np

# Largely mirrors open challenge, just with different internal logic and states

async def run_obstacle_challenge():
    async with Client() as client, AsyncMultiprocessingVisionProcessor() as vision, AsyncCamera() as camera:
        wall_follow = PD(1, 0.2)
        obstacle_avoid = PD(1, 0.2)
        corner_turn_controller = PD(1, 0.2)

        # Starting code here
        state: Literal["Straight", "Turn"] = "Straight"

        try:
            shm = shared_memory.SharedMemory(create=True, size=512*384*3, name="camera_frame")
        except FileExistsError:
            try:
                shm = shared_memory.SharedMemory(name="camera_frame")
                shm.close()
                shm.unlink()
                shm = shared_memory.SharedMemory(create=True, size=512*384*3, name="camera_frame") # Make sure it has exactly the size we need, and is empty
            except FileNotFoundError:
                # The shared memory segment disappeared between create and cleanup attempts, try again
                shm = shared_memory.SharedMemory(create=True, size=512*384*3, name="camera_frame")

        try:
            cam_receiver, cam_sender = mp.Pipe(duplex = False)
            camera_process = mp.Process(target = camera.stream, args=(cam_sender, shm.name,))
            camera_process.start()

            data_receiver, data_sender = mp.Pipe(duplex = False)
            vision_process = mp.Process(target = vision.comprehensive_analysis, args=(shm.name, data_sender, cam_receiver,))
            vision_process.start()

            # Camera process dumps frames into shared memory, and sends a signal through cam_sender when a new frame is ready.
            # Vision process listens on cam_receiver for the signal, then reads the frame from shared memory, processes it, and sends the results back through data_sender.
            # Staticmethod data_yielder polls the data_receiver for data and yields it to the main loop.

            async for zone, walls, obstacles, corner_lines, wall_x_diffs, obstacle_x_diffs, obstacle_path_x in AsyncMultiprocessingVisionProcessor.data_yielder(data_receiver):

                assert isinstance(zone, VisionObject)
                assert isinstance(walls, tuple) and all(isinstance(wall, VisionObject) for wall in walls)
                assert isinstance(obstacles, tuple) and all(isinstance(obstacle, VisionObject) for obstacle in obstacles)
                assert isinstance(corner_lines, tuple) and all(isinstance(line, VisionObject) for line in corner_lines)

                logger.debug(f"Zone: {zone}, Walls: {walls}, Obstacles: {obstacles}, Corner Lines: {corner_lines}, Wall Dists: {wall_x_diffs}, Obstacle Dists: {obstacle_x_diffs}, Obstacle Path X: {obstacle_path_x}")

                match state:
                    case "Straight":
                        if corner_lines:
                            state = "Turn"
                        else:
                            if obstacles:
                                turn_correction = obstacle_avoid.tick(obstacle_path_x)
                                asyncio.create_task(client.drive_motors(0.5, turn_correction, 0.1))
                            else:
                                turn_correction = wall_follow.tick(wall_x_diffs["left"] - wall_x_diffs["right"])
                                asyncio.create_task(client.drive_motors(0.5, turn_correction, 0.1))

                    case "Turn":
                        if not corner_lines:
                            state = "Straight"
                        else:
                            turn_correction = corner_turn_controller.tick(corner_lines[0].x_centroid - 192) # Biggest corner line, 192 is frame center
                            asyncio.create_task(client.drive_motors(0.5, turn_correction, 0.1))

                    case _:
                        logger.error(f"Invalid state {state}")
                        state = "Straight"
        finally:
            logger.info("Terminating processes and cleaning up shared memory...")
            try:
                camera_process.terminate()
                vision_process.terminate()
                shm.close()
                shm.unlink()
                logger.info("Exited cleanly")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
                logger.warning(f"Leaked memory segments and processes may need to be cleaned up manually. Good luck finding them michael -_-")