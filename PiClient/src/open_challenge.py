import asyncio
import sys
from typing import Literal
from loguru import logger
from commProtocol import Client
from visionProcessing import AsyncVisionProcessor, VisionObject
from asyncCamera import AsyncCamera
from src.controller import PD
import multiprocessing as mp
import cv2
import numpy as np

async def run():
    async with Client() as client, AsyncVisionProcessor() as vision, AsyncCamera() as camera:
        wall_follow = PD(1, 0.2)
        corner_turn_controller = PD(1, 0.2)

        # Starting code here
        state: Literal["Follow wall", "Turn"] = "Follow wall"
        look_ahead_task = None

        receiver, sender = mp.Pipe(duplex = False)

        camera_process = mp.Process(target = camera.stream, args=(sender,))
        camera_process.start()

        async for frame in AsyncCamera.frame_yielder(receiver):
            zone, walls, obstacles, corner_lines, wall_x_diffs, obstacle_dists = await vision.comprehensive_analysis(frame)

            assert isinstance(zone, VisionObject)
            assert isinstance(walls, tuple) and all(isinstance(wall, VisionObject) for wall in walls)
            assert isinstance(obstacles, tuple) and all(isinstance(obstacle, VisionObject) for obstacle in obstacles)
            assert isinstance(corner_lines, tuple) and all(isinstance(line, VisionObject) for line in corner_lines)

            logger.debug(f"Zone: {zone}, Walls: {walls}, Obstacles: {obstacles}, Corner Lines: {corner_lines}, Wall Dists: {wall_x_diffs}, Obstacle Dists: {obstacle_dists}")

            match state:
                case "Follow wall":
                    if look_ahead_task and look_ahead_task.done():
                        wall_x_diffs = look_ahead_task.result()
                    if corner_lines:
                        state = "Turn"
                        look_ahead_task = asyncio.create_task(vision.check_corner_lines(frame))
                    else:
                        turn_correction = wall_follow.tick(wall_x_diffs["left"] - wall_x_diffs["right"])
                        asyncio.create_task(client.drive_motors(0.5, turn_correction, 0.3)) # I really hopy my dt is at lot less then 0.3s, this is so it keeps going for a bit
                        # If like something silly happens with the os or some of my other processes

                case "Turn":
                    if look_ahead_task and look_ahead_task.done():
                        corner_lines = look_ahead_task.result()
                    if not corner_lines:
                        state = "Follow wall"
                        look_ahead_task = asyncio.create_task(vision.get_wall_distance(walls))
                    else:
                        turn_correction = corner_turn_controller.tick(corner_lines[0].x_centroid - 80) # Biggest corner line, 80 is frame center
                        asyncio.create_task(client.drive_motors(0.5, turn_correction, 0.3))

                case _:
                    logger.error(f"Invalid state {state}")
                    state = "Follow wall"