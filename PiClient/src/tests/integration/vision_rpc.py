import asyncio
import sys
from src import logger
from src.modules.comm_protocol import Client
from src.modules.vision_processing import AsyncMultiprocessingVisionProcessor, VisionObject
from src.modules.async_camera import AsyncCamera
from src.modules.subprocess_context_managers import camera_process_context_manager, vision_process_context_manager
from src.modules.config import Config
from multiprocessing import shared_memory
import multiprocessing as mp


async def run_tests():
    async with Client() as client:
        shm, camera_process, vision_process = None, None, None

        try:
            shm = shared_memory.SharedMemory(create=True, size=(Config.CameraConfig.OUTPUT_HEIGHT - Config.CameraConfig.INITIAL_ROI)
                                             * Config.CameraConfig.OUTPUT_WIDTH * Config.CameraConfig.OUTPUT_CHANNELS, name="camera_frame")
        except FileExistsError:
            try:
                shm = shared_memory.SharedMemory(name="camera_frame")
                shm.close()
                shm.unlink()
                shm = shared_memory.SharedMemory(create=True, size=(Config.CameraConfig.OUTPUT_HEIGHT - Config.CameraConfig.INITIAL_ROI)
                    * Config.CameraConfig.OUTPUT_WIDTH * Config.CameraConfig.OUTPUT_CHANNELS, name="camera_frame")
            except FileNotFoundError:
                shm = shared_memory.SharedMemory(create=True, size=(Config.CameraConfig.OUTPUT_HEIGHT - Config.CameraConfig.INITIAL_ROI)
                    * Config.CameraConfig.OUTPUT_WIDTH * Config.CameraConfig.OUTPUT_CHANNELS, name="camera_frame")
                
        try:

            cam_receiver, cam_sender = mp.Pipe(duplex=False)
            camera_process = mp.Process(
                target=camera_process_context_manager, args=(shm.name, cam_sender,))
            camera_process.start()

            data_receiver, data_sender = mp.Pipe(duplex=False)
            vision_process = mp.Process(target=vision_process_context_manager, args=(
                shm.name, cam_receiver, data_sender,))
            vision_process.start()

            async for zone, walls, obstacles, corner_lines, wall_dists, obstacle_dists in AsyncMultiprocessingVisionProcessor.async_pipe_reader(data_receiver):
            
                assert isinstance(
                    zone, VisionObject) or zone is None, f"Zone is not a VisionObject or None: {type(zone)}"

                assert isinstance(walls, tuple) and all(isinstance(wall, VisionObject)
                                                        for wall in walls), f"Walls is not a tuple of VisionObjects: {type(walls)} with elements {[type(wall) for wall in walls]}"

                assert isinstance(obstacles, tuple) and all(isinstance(obstacle, VisionObject)
                                                            for obstacle in obstacles), f"Obstacles is not a tuple of VisionObjects: {type(obstacles)} with elements {[type(obstacle) for obstacle in obstacles]}"

                assert isinstance(corner_lines, tuple) and all(isinstance(line, VisionObject)
                                                                for line in corner_lines), f"Corner lines is not a tuple of VisionObjects: {type(corner_lines)} with elements {[type(line) for line in corner_lines]}"

                assert isinstance(wall_dists, dict) and all(isinstance(dist, (int, float)) for dist in wall_dists.values(
                )), f"Wall distances is not a dict of numbers: {type(wall_dists)} with values {[type(dist) for dist in wall_dists.values()]}"

                assert isinstance(obstacle_dists, list) and all(
                    isinstance(item, tuple)
                    and len(item) == 2
                    and item[0] in ("left", "right")
                    and isinstance(item[1], (int, float))
                    for item in obstacle_dists
                ), f"Obstacle distances is not a list of (side, distance) tuples: {type(obstacle_dists)} with values {obstacle_dists}"

                # assert isinstance(obstacle_path_x, (int, float)), f"Obstacle path x is not numeric: {type(obstacle_path_x)}"

                if obstacles:
                    await client.drive_motors(0.25, 0, 0.5) # drive forward at 25% speed, 0 degrees steering, for 0.5 seconds when an obstacle is detected

                if zone:
                    await client.set_led_state(1)  # turn on LED when in a zone

                if walls:
                    await client.set_servo_angle(45)  # turn servo to 45 degrees when a wall is detected

        finally:
            if camera_process:
                camera_process.terminate() if camera_process.is_alive() else None
                camera_process.join()
            if vision_process:
                vision_process.terminate() if vision_process.is_alive() else None
                vision_process.join()
            if shm:
                shm.close()
                shm.unlink()
            