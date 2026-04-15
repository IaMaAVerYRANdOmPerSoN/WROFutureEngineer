from dataclasses import dataclass, field
from typing import Dict


class Config():

    @dataclass
    class CameraConfig():
        FORMAT: Dict = field(default_factory=lambda: {
            "format": "YUV420",
            "size": (384, 512)
        })
        INITIAL_ROI: int = 100
        EXECUTOR_THREADS: int = 3
        MAX_CONCURRENT_CAPTURES: int = 2
        BUFFER_COUNT: int = 2
        HW_INIT_TIMEOUT: float = 2.0
        CONFIGURE_TIMEOUT: float = 1.0
        START_TIMEOUT: float = 1.0
        CAPTURE_RETRY_SLEEP_SECONDS: float = 0.03
        CAPTURE_ERROR_SLEEP_SECONDS: float = 0.01
        SENSOR_CONFIG: Dict = field(default_factory=lambda: {
            "output_size": (640, 480),
            "bit_depth": 10
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
        SERVO_MIN_ANGLE: int = -180
        SERVO_MAX_ANGLE: int = 180

    @dataclass
    class VisionConfig():
        PERSPECTIVE_TRANSFORM: tuple = (
            (0, 0, 0),
            (0, 0, 0),
            (0, 0, 0)
            # 3x3 homography matrix use VisionProcessor.get_perspective_transform() to set this up with actual points
        )
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
        DEFAULT_FRAME_WIDTH: int = 512
        MIN_CENTROID_Y: int = 30
        ANALYSIS_FRAME_WIDTH: int = 512
        ANALYSIS_FRAME_HEIGHT: int = 384
        ANALYSIS_FRAME_CHANNELS: int = 3

    @dataclass
    class OpenChallengeConfig():
        WALL_FOLLOW_KPKD: tuple = (1, 0.2)
        CORNER_TURN_KPKD: tuple = (1.2, 0.2)
        DRIVE_SPEED: float = 0.5
        DRIVE_COMMAND_DURATION: float = 0.1
        SHM_NAME: str = "camera_frame"
        SHM_SIZE: int = 512*384*3
