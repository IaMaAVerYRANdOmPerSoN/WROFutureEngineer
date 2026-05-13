from dataclasses import dataclass, field
from typing import ClassVar, Dict, Tuple
import numpy as np


class Config():

    @dataclass
    class CameraConfig():
        FORMAT: Dict = field(default_factory=lambda: {
            "format": "YUV420",
            # Camera API expects (width, height); NumPy/OpenCV arrays usually use (height, width).
            "size": (512, 384)
        })
        OUTPUT_WIDTH: int = 512
        OUTPUT_HEIGHT: int = 384
        OUTPUT_CHANNELS: int = 3
        INITIAL_ROI: int = 110
        EXECUTOR_THREADS: int = 3
        MAX_CONCURRENT_CAPTURES: int = 3
        BUFFER_COUNT: int = 1
        HW_INIT_TIMEOUT: float = 5.0
        CONFIGURE_TIMEOUT: float = 1.0
        START_TIMEOUT: float = 1.0
        CAPTURE_RETRY_SLEEP_SECONDS: float = 0.03
        CAPTURE_ERROR_SLEEP_SECONDS: float = 0.01
        SENSOR_CONFIG: Dict = field(default_factory=lambda: {
            "output_size": (640, 480),
            "bit_depth": 10,
        })

        CONTROLS_CONFIG: Dict = field(default_factory=lambda: {
            "FrameDurationLimits": (33333, 33333),
            "AeEnable": True,
        })

    @dataclass
    class ClientConfig():
        SERIAL_PORT: str = '/dev/ttyACM0'
        SERIAL_BAUD: int = 115200
        SERIAL_TIMEOUT: float = 0.3
        REQUEST_TIMEOUT: float = 2.0
        WAIT_PATTERN: str = r"WAITMS ([0-9]+)"
        WAIT_RE_PATTERN: str = WAIT_PATTERN
        WAIT_RESPONSE_EXTRA_SECONDS: float = 0.5
        TID_START: int = 1
        TID_END: int = 500
        WHEELBASE: float = 0.1
        MAX_SPEED: int = 100
        CONNECT_RETRIES: int = 5
        CONNECT_RETRY_SLEEP_SECONDS: float = 0.5
        SERVO_MIN_ANGLE: int = 0
        SERVO_MAX_ANGLE: int = 180

    @dataclass
    class VisionConfig():
        PERSPECTIVE_TRANSFORM: ClassVar[np.ndarray] = np.array([
            [1, 0, 0],
            [0, 1, 0],
            [0, 0, 1]
        ], dtype=np.float32)
        # Not tuned, also uv plane only
        # TODO: Change this to full YUV, and autotuning soonTM (or if I get bored perhaps)
        LOWER_BLUE: Tuple[int, int, int] = (35, 140, 70)
        UPPER_BLUE: Tuple[int, int, int] = (255, 200, 130)
        LOWER_ORANGE: Tuple[int, int, int] = (60, 50, 140)
        UPPER_ORANGE: Tuple[int, int, int] = (255, 130, 220)
        LOWER_GREEN: Tuple[int, int] = (40, 50)
        UPPER_GREEN: Tuple[int, int] = (80, 255)
        LOWER_RED: Tuple[int, int] = (0, 100)
        UPPER_RED: Tuple[int, int] = (10, 255)

        # Only check y plane for black/white since we don't give a damn about color
        LOWER_BLACK: Tuple[int, int, int] = (0, 100, 100)
        UPPER_BLACK: Tuple[int, int, int] = (80, 140, 140)
        LOWER_WHITE: int = 180
        UPPER_WHITE: int = 255
        DEFAULT_FRAME_WIDTH: int = 512
        MIN_CENTROID_Y: int = 30
        ANALYSIS_FRAME_WIDTH: int = 512
        ANALYSIS_FRAME_HEIGHT: int = 384
        ANALYSIS_FRAME_CHANNELS: int = 3

    @dataclass
    class OpenChallengeConfig():
        WALL_FOLLOW_KPKD: Tuple[float, float] = (1, 0.2)
        CORNER_TURN_KPKD: Tuple[float, float] = (1.2, 0.2)
        STRAIGHT_SPEED: float = 0.5
        TURN_SPEED: float = 0.3
        TURN_ANGLE: float = 80.0
        TURN_DURATION: float = 1.0
        DRIVE_COMMAND_DURATION: float = 0.1
        SHM_NAME: str = "camera_frame"
        SHM_SIZE: int = 512*384*3
        TURN_HYSTERESIS: int = 5
        LAP_LENGTH_IN_TURNS: int = 4*3  # 4 turns per lap, 3 laps total

    @dataclass
    class ObstacleChallengeConfig():
        WALL_FOLLOW_KPKD: Tuple[float, float] = (1, 0.2)
        CORNER_TURN_KPKD: Tuple[float, float] = (1.2, 0.2)
        OBSTACLE_AVOID_KPKD: Tuple[float, float] = (0.8, 0.1)
        STRAIGHT_SPEED: float = 0.5
        TURN_SPEED: float = 0.3
        HYBRID_SPEED: float = 0.4
        DRIVE_COMMAND_DURATION: float = 0.1
        SHM_NAME: str = "camera_frame"
        SHM_SIZE: int = 512*384*3
        LAP_LENGTH_IN_TURNS: int = 4*3  # 4 turns per lap, 3 laps total

    @dataclass
    class LiDARConfig():
        SERIAL_PORT: str = '/dev/ttyAMA0'
        SERIAL_BAUD: int = 230400
        SERIAL_TIMEOUT: float = 0.1
        PACKET_HEADER: int = 0x54
        PACKET_VER_LEN: int = 0x2C
        PACKET_LEN: int = 47
