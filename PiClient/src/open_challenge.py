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

async def run():
    async with Client() as client, AsyncMultiprocessingVisionProcessor() as vision, AsyncCamera() as camera:
        wall_follow = PD(1, 0.2)
        corner_turn_controller = PD(1, 0.2)

        # Starting code here
        state: Literal["Follow wall", "Turn"] = "Follow wall"

        try:
            shm = shared_memory.SharedMemory(create=True, size=512*384*3, name="camera_frame")
        except FileExistsError:
            try:
                shm = shared_memory.SharedMemory(name="camera_frame")
                shm.close()
                shm.unlink()
                shm = shared_memory.SharedMemory(create=True, size=512*384*3, name="camera_frame") # Nake sure it has excatly the size we need, and is empty
            except FileNotFoundError:
                # The shared memory segment disappeared between create and cleanup attempts, try again
                shm = shared_memory.SharedMemory(create=True, size=512*384*3, name="camera_frame")


        try:
            _, cam_sender = mp.Pipe(duplex = False)
            camera_process = mp.Process(target = camera.stream, args=(cam_sender, shm.name,))
            camera_process.start()

            data_receiver, data_sender = mp.Pipe(duplex = False)
            vision_process = mp.Process(target = vision.comprehensive_analysis, args=(shm.name, data_sender, data_receiver,))
            vision_process.start()

            # Camera process dumps frames into shared memory, and sends a signal through cam_sender when a new frame is ready.
            # Vision process does the same with the analysis results and data_sender.
            # Saticmethod data_yielder polls the receier for data and yeilds it to to the main loop.

            async for zone, walls, obstacles, corner_lines, wall_x_diffs, obstacle_dists in AsyncMultiprocessingVisionProcessor.data_yielder(data_receiver):

                assert isinstance(zone, VisionObject)
                assert isinstance(walls, tuple) and all(isinstance(wall, VisionObject) for wall in walls)
                assert isinstance(obstacles, tuple) and all(isinstance(obstacle, VisionObject) for obstacle in obstacles)
                assert isinstance(corner_lines, tuple) and all(isinstance(line, VisionObject) for line in corner_lines)

                logger.debug(f"Zone: {zone}, Walls: {walls}, Obstacles: {obstacles}, Corner Lines: {corner_lines}, Wall Dists: {wall_x_diffs}, Obstacle Dists: {obstacle_dists}")

                match state:
                    case "Follow wall":
                        if corner_lines:
                            state = "Turn"
                        else:
                            turn_correction = wall_follow.tick(wall_x_diffs["left"] - wall_x_diffs["right"])
                            asyncio.create_task(client.drive_motors(0.5, turn_correction, 0.1)) # I really hopy my dt is at lot less then 0.1s, this is so it keeps going for a bit
                            # If like something silly happens with the os or some of my other processes

                    case "Turn":
                        if not corner_lines:
                            state = "Follow wall"
                        else:
                            turn_correction = corner_turn_controller.tick(corner_lines[0].x_centroid - 192) # Biggest corner line, 192 is frame center
                            asyncio.create_task(client.drive_motors(0.5, turn_correction, 0.1))

                    case _:
                        logger.error(f"Invalid state {state}")
                        state = "Follow wall"
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