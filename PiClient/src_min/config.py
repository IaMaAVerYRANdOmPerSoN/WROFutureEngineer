from dataclasses import dataclass, field
from typing import Dict, Tuple


class Config:
    @dataclass
    class CameraConfig:
        FORMAT: Dict = field(default_factory=lambda: {"format": "YUV420", "size": (512, 384)})
        INITIAL_ROI: int = 100
        SENSOR_CONFIG: Dict = field(default_factory=lambda: {
            "output_size": (640, 480),
            "bit_depth": 10,
        })
        CONTROLS_CONFIG: Dict = field(default_factory=lambda: {
            "FrameDurationLimits": (33333, 33333),
            "AeEnable": True,
        })
        BUFFER_COUNT: int = 2
        YUV_SUBSAMPLE_DIVISOR: int = 2

    @dataclass
    class ClientConfig:
        SERIAL_PORT: str = "/dev/ttyACM0"
        SERIAL_BAUD: int = 115200
        SERIAL_TIMEOUT: float = 0.3
        REQUEST_TIMEOUT: float = 2.0
        WAIT_RESPONSE_EXTRA_SECONDS: float = 0.5
        CONNECT_RETRIES: int = 5
        CONNECT_RETRY_DELAY_SECONDS: float = 0.5
        WAIT_PATTERN: str = r"WAITMS ([0-9]+)"
        TID_START: int = 1
        TID_END: int = 500
        WHEELBASE: float = 0.1
        MAX_SPEED: int = 100
        SERVO_MIN_ANGLE: int = -180
        SERVO_MAX_ANGLE: int = 180

    @dataclass
    class VisionConfig:
        PERSPECTIVE_TRANSFORM: Tuple[Tuple[int, int, int], ...] = (
            (0, 0, 0),
            (0, 0, 0),
            (0, 0, 0),
        )

        LOWER_BLUE: Tuple[int, int] = (216, 63)
        UPPER_BLUE: Tuple[int, int] = (255, 103)
        LOWER_ORANGE: Tuple[int, int] = (33, 194)
        UPPER_ORANGE: Tuple[int, int] = (73, 234)
        LOWER_GREEN: Tuple[int, int] = (0, 0)
        UPPER_GREEN: Tuple[int, int] = (110, 110)
        LOWER_RED: Tuple[int, int] = (100, 140)
        UPPER_RED: Tuple[int, int] = (130, 255)

        LOWER_BLACK: int = 0
        UPPER_BLACK: int = 100
        LOWER_WHITE: int = 200
        UPPER_WHITE: int = 255

        DEFAULT_FRAME_WIDTH: int = 512
        MIN_CENTROID_Y: int = 30

    @dataclass
    class OpenChallengeConfig:
        WALL_FOLLOW_KPKD: Tuple[float, float] = (1, 0.2)
        CORNER_TURN_KPKD: Tuple[float, float] = (1, 0.2)
        DRIVE_SPEED: float = 0.5
        DRIVE_COMMAND_DURATION: float = 0.1
        FRAME_CENTER_X: int = 192
