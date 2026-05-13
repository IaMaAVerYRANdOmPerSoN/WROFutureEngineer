# simplest shit possible - no MP, HSV frames directly
import cv2
import numpy as np
from math import isinf
from src.modules.comm_protocol import Client
from src.modules.config import Config
from src.modules.controller import PD
from src import logger
from typing import Literal


async def run_simple_open_challenge():
    # Setup camera in HSV
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
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
        state: Literal["Follow wall", "Turn"] = "Follow wall"
        state_history = [state, 0]  # tracks how long we've been in a state
        turn_counter = 0

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    logger.error("Failed to capture frame")
                    continue
                
                # Convert to HSV directly
                hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                
                # Simple wall detection: look for black/dark lines (low V in HSV)
                # Walls are typically low V values in HSV
                v_channel: cv2.typing.MatLike = hsv_frame[:, :, 2]
                wall_mask = cv2.inRange(v_channel, np.array(0), np.array(100))
                
                # Detect left and right walls (simple: split frame vertically)
                height, width = wall_mask.shape
                left_half = wall_mask[:, :width//2]
                right_half = wall_mask[:, width//2:]
                
                left_wall_pixels = cv2.countNonZero(left_half)
                right_wall_pixels = cv2.countNonZero(right_half)
                
                # Calculate wall distances (normalized)
                wall_x_diffs = {
                    "left": left_wall_pixels / (height * width//2) if height * width//2 > 0 else float('inf'),
                    "right": right_wall_pixels / (height * width//2) if height * width//2 > 0 else float('inf')
                }
                
                # Corner detection: look for blue (left turn) and orange (right turn) colored lines
                # Blue in HSV: H ~100-130, Orange in HSV: H ~10-25

                blue_mask = cv2.inRange(hsv_frame, np.array([100, 100, 100], dtype=np.uint8), np.array([130, 255, 255], dtype=np.uint8))
                orange_mask = cv2.inRange(hsv_frame, np.array([10, 100, 100], dtype=np.uint8), np.array([25, 255, 255], dtype=np.uint8))
                
                image = cv2.addWeighted(hsv_frame, 0.7, wall_mask, 0.3, 0)
                cv2.imshow("debug", image)
                if cv2.waitKey(0) == ord("q"):
                    cv2.destroyAllWindows()
                    break
                
                blue_pixels = cv2.countNonZero(blue_mask)
                orange_pixels = cv2.countNonZero(orange_mask)
                
                corner_lines = []
                if blue_pixels > 100:  # threshold to avoid noise
                    corner_lines.append(type('VisionObject', (), {'color': 'blue'})())
                elif orange_pixels > 100:
                    corner_lines.append(type('VisionObject', (), {'color': 'orange'})())
                
                logger.debug(
                    f"Wall Dists: {wall_x_diffs}, Corner Lines: {[c.color for c in corner_lines]}")
                
                state_history[1] = (state_history[1] +
                                    1 if state_history[0] == state else 0)

                if state_history[0] == "Turn" and state != "Turn" and state_history[1] > Config.OpenChallengeConfig.TURN_HYSTERESIS:
                    turn_counter += 1
                    if turn_counter > Config.OpenChallengeConfig.LAP_LENGTH_IN_TURNS:
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
                            await client.drive_motors(
                                Config.OpenChallengeConfig.STRAIGHT_SPEED,
                                turn_correction,
                                Config.OpenChallengeConfig.DRIVE_COMMAND_DURATION,
                            )

                    case "Turn":
                        if state_history[1] > Config.OpenChallengeConfig.TURN_HYSTERESIS and corner_lines:
                            if corner_lines[0].color == "blue":  # Left turn
                                await client.drive_motors(
                                    Config.OpenChallengeConfig.TURN_SPEED,
                                    -Config.OpenChallengeConfig.TURN_ANGLE,
                                    Config.OpenChallengeConfig.TURN_DURATION,
                                )
                            elif corner_lines[0].color == "orange":
                                await client.drive_motors(
                                    Config.OpenChallengeConfig.TURN_SPEED,
                                    Config.OpenChallengeConfig.TURN_ANGLE,
                                    Config.OpenChallengeConfig.TURN_DURATION,
                                )
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
            logger.info("Cleaning up...")
            try:
                await client.drive_motors(0, 0, 0)  # Stop the robot
                cap.release()
                logger.info("Done")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
