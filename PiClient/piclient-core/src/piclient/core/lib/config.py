"""Centralised configuration for the Pi Client.

Contains nested dataclasses for camera, serial client, vision processing,
and challenge-specific tuning parameters.
"""

from dataclasses import dataclass, field
from typing import ClassVar, Dict, Tuple
import numpy as np
from .exporter import export


@export
class Config:
    """Root configuration container.

    All configuration is organised into nested :class:`dataclass` subclasses.
    Each subclass defines default values that can be overridden at runtime.
    """

    @dataclass
    class CameraConfig:
        """Camera hardware and frame-capture settings.

        Controls picamera2 format, resolution, thread pool size,
        timeouts, and sensor/control parameters.
        """
        FORMAT: Dict = field(default_factory=lambda: {
            "format": "BGR888",
            # Camera API expects (width, height); NumPy/OpenCV arrays usually use (height, width).
            "size": (512, 384)
        })
        OUTPUT_WIDTH: int = 512
        OUTPUT_HEIGHT: int = 384
        OUTPUT_CHANNELS: int = 3
        EXECUTOR_THREADS: int = 3 # Number of executor threads used to capture frames
        MAX_CONCURRENT_CAPTURES: int = 3 
        BUFFER_COUNT: int = 1
        HW_INIT_TIMEOUT: float = 5.0 # Hardware
        CONFIGURE_TIMEOUT: float = 1.0
        START_TIMEOUT: float = 1.0
        CAPTURE_RETRY_SLEEP_SECONDS: float = 0.03
        CAPTURE_ERROR_SLEEP_SECONDS: float = 0.01
        SENSOR_CONFIG: Dict = field(default_factory=lambda: {
            "output_size": (640, 480),
            "bit_depth": 10,
        })

        CONTROLS_CONFIG: Dict = field(default_factory=lambda: {
            "FrameDurationLimits": (33333, 33333), # Frame duration in nano/micro seconds
            "AeEnable": True, # Enables automatic exposure
        })

    @dataclass
    class ClientConfig:
        """Serial client communication settings.

        Defines the serial port, baud rate, timeouts, TID range,
        servo limits, and motor parameters.
        """
        SERIAL_PORT: str = '/dev/ttyACM0' 
        SERIAL_BAUD: int = 115200 
        SERIAL_TIMEOUT: float = 0.3 
        REQUEST_TIMEOUT: float = 2.0 
        WAIT_PATTERN: str = r"WAITMS ([0-9]+)" # Regex for wait ms responce
        WAIT_RE_PATTERN: str = WAIT_PATTERN 
        WAIT_RESPONSE_EXTRA_SECONDS: float = 1 
        TID_START: int = 1 # Last transaction ID 
        TID_END: int = 500 # Last transaction ID before cycling to 1
        WHEELBASE: float = 0.1
        MAX_SPEED: int = 100
        CONNECT_RETRIES: int = 5
        CONNECT_RETRY_SLEEP_SECONDS: float = 0.5
        SERVO_MIN_ANGLE: int = 0
        SERVO_MAX_ANGLE: int = 180

    @dataclass
    class VisionConfig:
        """Vision processing parameters.

        Includes the perspective-transform homography matrix, HSV colour
        thresholds for wall/line detection, and region-of-interest slices.
        """
        PERSPECTIVE_TRANSFORM: ClassVar[np.ndarray] = np.array([ 
            [1, 0, 0],
            [0, 1, 0],
            [0, 0, 1]
        ], dtype=np.float32) # Hemography matrix

        LOWER_BLACK: Tuple[int, int, int] = (0, 0, 0)
        UPPER_BLACK: Tuple[int, int, int] = (179, 255, 70)

        # 384 // 3 = 128
        # 384 - 384 // 8 = 336
        # 336 - 128 = 208

        INITIAL_ROI: Tuple = np.s_[384 // 3 : 384 - 384 // 8, :, :]
        LEFT_WALL_ROI: Tuple = np.s_[208 // 12: 208 - 208 // 5, :512 // 5]
        RIGHT_WALL_ROI: Tuple = np.s_[208 // 12: 208 - 208 // 5, 512 - 512 // 5:]

    @dataclass
    class OpenChallengeConfig:
        """Tuning parameters for the Open Challenge.

        Includes PD gains, speeds, hysteresis thresholds, shared memory
        settings, and lap-length constants.
        """
        WALL_FOLLOW_KPKD: Tuple[float, float] = (0.50, 0.0)
        CORNER_TURN_KPKD: Tuple[float, float] = (0.55, 0.0)
        STRAIGHT_SPEED: float = -0.4
        TURN_SPEED: float = -0.33
        TURN_DURATION: float = 1.0
        DRIVE_COMMAND_DURATION: float = 0.2
        SHM_NAME: str = "camera_frame" 
        SHM_SIZE: int = 512*384*3
        TURN_HYSTERESIS: int = 6 # Number of frames deciding before changing states
        LAP_LENGTH_IN_TURNS: int = 4*3  # 4 turns per lap, 3 laps total
        TURN_DETECTION_THRESHOLD: float = 0.1

    @dataclass
    class ObstacleChallengeConfig:
        """Tuning parameters for the Obstacle Challenge.

        Includes PD gains for wall-following, corner turning, and obstacle
        avoidance, along with speeds and shared memory settings.
        """
        WALL_FOLLOW_KPKD: Tuple[float, float] = (1, 0.2)
        CORNER_TURN_KPKD: Tuple[float, float] = (1.2, 0.2)
        OBSTACLE_AVOID_KPKD: Tuple[float, float] = (0.8, 0.1)
        STRAIGHT_SPEED: float = 0.5
        TURN_SPEED: float = 0.4
        HYBRID_SPEED: float = 0.4
        DRIVE_COMMAND_DURATION: float = 0.1
        SHM_NAME: str = "camera_frame"
        SHM_SIZE: int = 512*384*3
        LAP_LENGTH_IN_TURNS: int = 4*3  # 4 turns per lap, 3 laps total

    @dataclass
    class LiDARConfig:
        """LD19 LiDAR serial and packet settings.

        Defines the UART port, baud rate, packet framing constants,
        and timeouts.
        """
        SERIAL_PORT: str = '/dev/ttyAMA0'
        SERIAL_BAUD: int = 230400
        SERIAL_TIMEOUT: float = 0.1
        PACKET_HEADER: int = 0x54
        PACKET_VER_LEN: int = 0x2C
        PACKET_LEN: int = 47
