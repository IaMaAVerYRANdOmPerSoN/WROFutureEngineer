from typing import Literal
from loguru import logger
from .camera import Camera
from .commProtocol import Client
from .controller import PD
from .visionProcessing import VisionObject, VisionProcessor

def run():
    vision = VisionProcessor()
    with Client() as client, Camera() as camera:
        wall_follow = PD(1, 0.2)
        corner_turn_controller = PD(1, 0.2)

        # Starting code here
        state: Literal["Follow wall", "Turn"] = "Follow wall"

        if not client.verify_connection():
            return

        while True:
            frame = camera.get_frame()
            zone, walls, obstacles, corner_lines, wall_x_diffs, obstacle_dists = vision.comprehensive_analysis(frame)

            if zone is not None:
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
                        client.drive_motors(0.5, turn_correction, 0.1)

                case "Turn":
                    if not corner_lines:
                        state = "Follow wall"
                    else:
                        turn_correction = corner_turn_controller.tick(corner_lines[0].x_centroid - 192) # Biggest corner line, frame center
                        client.drive_motors(0.5, turn_correction, 0.1)

                case _:
                    logger.error(f"Invalid state {state}")
                    state = "Follow wall"