from dataclasses import dataclass
from typing import Dict

class Config():

    @dataclass
    class CameraConfig():
        FORMAT: Dict = {"format": "YUV420", "size": (384, 512)}
        INITIAL_ROI: int = 100
        EXECUTOR_THREADS: int = 3
        MAX_CONCURRENT_CAPTURES: int = 2
        SENSOR_CONFIG: Dict = {
                "output_size": (640, 480),
                "bit_depth": 10
            }

        CONTROLS_CONFIG: Dict = {
                "FrameDurationLimits": (33333, 33333), 
                "AeEnable": True, 
        }

    @dataclass
    class ClientConfig():
        SERIAL_PORT: str = '/dev/ttyACM0'
        SERIAL_BAUD: int = 115200
        SERIAL_TIMEOUT: float = 0.3
        MAX_SPEED: int = 100

    @dataclass
    class VisionConfig():
        PERSPECTIVE_TRANSFORM: tuple = (
                (0, 0, 0), 
                (0, 0, 0), 
                (0, 0, 0)
        ) # 3x3 homography matrix use VisionProcessor.get_perspective_transform() to set this up with actual points
        # Not tunnned, also uv plane only
        # TODO: Change this to full YUV, and autotuning soonTM (or if I get boared perhaps)
        LOWER_BLUE: tuple = (100, 150)
        UPPER_BLUE: tuple = (140, 255)
        LOWER_ORANGE: tuple = (10, 100)
        UPPER_ORANGE: tuple = (25, 255)
        LOWER_GREEN: tuple = (40, 50)
        UPPER_GREEN: tuple = (80, 255)
        LOWER_RED: tuple = (0, 100)
        UPPER_RED: tuple = (10, 255)

        # Only check y plane for black/white since we don't give a damn about color
        LOWER_BLACK: int = 0
        UPPER_BLACK: int = 50
        LOWER_WHITE: int = 200
        UPPER_WHITE: int = 255

    @dataclass
    class OpenChallengeConfig():
        WALL_FOLLOW_KPKD: tuple = (1, 0.2)
        CORNER_TURN_KPKD: tuple = (1.2, 0.2)
        SHM_NAME: str = "camera_frame"
        SHM_SIZE: int = 512*384*3