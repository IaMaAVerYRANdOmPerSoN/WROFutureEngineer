from typing import Literal, Sequence
from math import isinf
import numpy as np
from loguru import logger
from .camera import Camera
from .commProtocol import Client
from .controller import PD
from .visionProcessing import VisionObject, VisionProcessor
from .config import Config


def run_open_challenge():
    vision = VisionProcessor()
    with Client() as client, Camera() as camera:
        wall_follow = PD(*Config.OpenChallengeConfig.WALL_FOLLOW_KPKD)
        corner_turn_controller = PD(
            *Config.OpenChallengeConfig.CORNER_TURN_KPKD)

        # Starting code here
        state: Literal["Follow wall", "Turn", "Hybrid"] = "Follow wall"
        state_history = [state, 0]
        turn_counter = 0

        if not client.verify_connection():
            return

        try:
            while True:
                frame = camera.get_frame()
                zone, walls, obstacles, corner_lines, wall_x_diffs, obstacle_dists, _ = vision.comprehensive_analysis(
                    frame)

                if zone is not None:
                    assert isinstance(zone, VisionObject)
                    assert isinstance(walls, tuple) and all(
                        isinstance(wall, VisionObject) for wall in walls)
                    assert isinstance(obstacles, tuple) and all(
                        isinstance(obstacle, VisionObject) for obstacle in obstacles)
                    assert isinstance(corner_lines, tuple) and all(
                        isinstance(line, VisionObject) for line in corner_lines)

                logger.debug(
                    f"Zone: {zone}, Walls: {walls}, Obstacles: {obstacles}, Corner Lines: {corner_lines}, Wall Dists: {wall_x_diffs}, Obstacle Dists: {obstacle_dists}")

                state_history[1] = (state_history[1] +
                                    1 if state_history[0] == state else 0)
                state_history[0] = state

                if (
                    state_history[0] == "Turn"
                    and state_history[1] > Config.OpenChallengeConfig.TURN_HYSTERESIS
                    and not corner_lines
                ):
                    turn_counter += 1
                    if turn_counter >= Config.OpenChallengeConfig.LAP_LENGTH_IN_TURNS:
                        break

                match state:
                    case "Follow wall":
                        if any(isinf(x_diff) for x_diff in wall_x_diffs.values()):
                            corner_turn_controller.previous_error = 0
                            state = "Turn"

                        elif corner_lines:
                            corner_turn_controller.previous_error = 0
                            state = "Hybrid"

                        else:
                            turn_correction = wall_follow.tick(
                                wall_x_diffs["left"] - wall_x_diffs["right"])
                            client.drive_motors(
                                Config.OpenChallengeConfig.STRAIGHT_SPEED,
                                turn_correction,
                                Config.OpenChallengeConfig.DRIVE_COMMAND_DURATION,
                            )

                    case "Turn":
                        if not corner_lines:
                            wall_follow.previous_error = 0
                            state = "Follow wall"

                        elif not any(isinf(x_diff) for x_diff in wall_x_diffs.values()):
                            wall_follow.previous_error = 0
                            state = "Hybrid"

                        else:
                            turn_correction = corner_turn_controller.tick(
                                corner_lines[0].x_centroid
                                - Config.CameraConfig.FORMAT["size"][0] // 2
                            )
                            client.drive_motors(
                                Config.OpenChallengeConfig.TURN_SPEED,
                                turn_correction,
                                Config.OpenChallengeConfig.DRIVE_COMMAND_DURATION,
                            )

                    case "Hybrid":
                        if not corner_lines:
                            wall_follow.previous_error = 0
                            state = "Follow wall"

                        if any(isinf(x_diff) for x_diff in wall_x_diffs.values()):
                            corner_turn_controller.previous_error = 0
                            state = "Turn"

                        else:
                            turn_correction = (
                                wall_follow.tick(
                                    wall_x_diffs["left"] - wall_x_diffs["right"])
                                + corner_turn_controller.tick(
                                    corner_lines[0].x_centroid
                                    - Config.CameraConfig.FORMAT["size"][0] // 2
                                )
                            ) // 2
                            client.drive_motors(
                                Config.OpenChallengeConfig.HYBRID_SPEED,
                                turn_correction,
                                Config.OpenChallengeConfig.DRIVE_COMMAND_DURATION,
                            )

                    case _:
                        logger.error(f"Invalid state {state}")
                        if not corner_lines and not any(isinf(x_diff) for x_diff in wall_x_diffs.values()):
                            wall_follow.previous_error = 0
                            state = "Follow wall"

                        corner_turn_controller.previous_error = 0
                        state = "Turn"
        finally:
            logger.info("Stopping...")
            client.drive_motors(0, 0, 0)  # Stop the robot
            logger.success("Done")


class OpenChallengeVisionProcessor(VisionProcessor):
    def __init__(self, *args, **kwargs):
        super(OpenChallengeVisionProcessor, self).__init__(*args, **kwargs)

    # Bogus overwrite to disable perspective transforms on basic version
    def _perspective_transform(self, contours: Sequence[VisionObject], colors: Sequence[str]) -> Sequence[VisionObject]:
        return np.array([VisionObject(contour=contour, color=color) for contour, color in zip(contours, colors)])
