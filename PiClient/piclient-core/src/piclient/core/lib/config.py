"""Centralised configuration for the Pi Client.

Contains nested dataclasses for camera, serial client, vision processing,
and challenge-specific tuning parameters.
"""

from dataclasses import dataclass, field
import dataclasses
from typing import Any, Literal
import numpy as np
from .exporter import export

from tomllib import load as load_toml


@export
class Config:
    """Root configuration container.

    All configuration is organised into nested :class:`dataclass` subclasses.
    Each subclass is instantiated at construction time.
    """

    def __init__(self) -> None:
        for name in dir(type(self)):
            if name.startswith("_"):
                continue
            cls: type | None = getattr(type(self), name, None)
            if dataclasses.is_dataclass(cls):
                setattr(self, name, cls())

    @dataclass
    class GeneralConfig:
        """
        General Configuration.
        
        Controls logging level and which challenge to ru
        """
        LEVEL: Literal["CRITICAL", "ERROR", "WARNING", "SUCCESS", "INFO", "DEBUG"] = "WARNING"
        CHALLENGE: Literal["open", "obstacle"] = "open"

    @dataclass
    class CameraConfig:
        """Camera hardware and frame-capture settings.

        Controls picamera2 format, resolution, thread pool size,
        timeouts, and sensor/control parameters.
        """
        FORMAT: dict[str, Any] = field(default_factory=lambda: {
            "format": "BGR888",
            # Camera API expects (width, height); NumPy/OpenCV arrays usually use (height, width).
            "size": (512, 384)
        })
        OUTPUT_WIDTH: int = 512
        OUTPUT_HEIGHT: int = 384
        OUTPUT_CHANNELS: int = 3
        EXECUTOR_THREADS: int = 3  # Number of executor threads used to capture frames
        MAX_CONCURRENT_CAPTURES: int = 3
        BUFFER_COUNT: int = 1
        HW_INIT_TIMEOUT: float = 5.0  # Hardware
        CONFIGURE_TIMEOUT: float = 1.0
        START_TIMEOUT: float = 1.0
        CAPTURE_RETRY_SLEEP_SECONDS: float = 0.03
        CAPTURE_ERROR_SLEEP_SECONDS: float = 0.01
        SENSOR_CONFIG: dict[str, Any] = field(default_factory=lambda: {
            "output_size": (640, 480),
            "bit_depth": 10,
        })

        CONTROLS_CONFIG: dict[str, Any] = field(default_factory=lambda: {
            # Frame duration in microseconds
            "FrameDurationLimits": (33333, 33333),
            "AeEnable": True,  # Enables automatic exposure
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
        WAIT_PATTERN: str = r"WAITMS ([0-9]+)"  # Regex for wait ms responce
        WAIT_RE_PATTERN: str = WAIT_PATTERN
        WAIT_RESPONSE_EXTRA_SECONDS: float = 1
        TID_START: int = 1  # First transaction ID
        TID_END: int = 500  # Last transaction ID before cycling to TID_START
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
        PERSPECTIVE_TRANSFORM: np.ndarray[tuple[int, ...], np.dtype[np.float32 | np.float64]] = field(default_factory = lambda: np.array([
            [1, 0, 0],
            [0, 1, 0],
            [0, 0, 1]
        ], dtype=np.float32))  # Homography matrix

        LOWER_BLACK: tuple[int, int, int] = (0, 0, 0)
        UPPER_BLACK: tuple[int, int, int] = (179, 255, 70)

        # 384 // 3 = 128
        # 384 - 384 // 8 = 336
        # 336 - 128 = 208

        INITIAL_ROI: tuple[slice, slice, slice] = np.s_[
            384 // 3: 384 - 384 // 8, :, :]
        LEFT_WALL_ROI: tuple[slice, slice] = np.s_[
            208 // 12: 208 - 208 // 5, :512 // 5]
        RIGHT_WALL_ROI: tuple[slice, slice] = np.s_[
            208 // 12: 208 - 208 // 5, 512 - 512 // 5:]

    @dataclass
    class OpenChallengeConfig:
        """Tuning parameters for the Open Challenge.

        Includes PD gains, speeds, hysteresis thresholds, shared memory
        settings, and lap-length constants.
        """
        WALL_FOLLOW_KPKD: tuple[float, float] = (0.50, 0.0)
        CORNER_TURN_KPKD: tuple[float, float] = (0.55, 0.0)
        STRAIGHT_SPEED: float = -0.4
        TURN_SPEED: float = -0.33
        TURN_DURATION: float = 1.0
        DRIVE_COMMAND_DURATION: float = 0.2
        SHM_NAME: str = "camera_frame"
        SHM_SIZE: int = 512*384*3
        TURN_HYSTERESIS: int = 6  # Number of frames deciding before changing states
        LAP_LENGTH_IN_TURNS: int = 4*3  # 4 turns per lap, 3 laps total
        TURN_DETECTION_THRESHOLD: float = 0.1

    @dataclass
    class ObstacleChallengeConfig:
        """Tuning parameters for the Obstacle Challenge.

        Includes PD gains for wall-following, corner turning, and obstacle
        avoidance, along with speeds and shared memory settings.
        """
        WALL_FOLLOW_KPKD: tuple[float, float] = (1, 0.2)
        CORNER_TURN_KPKD: tuple[float, float] = (1.2, 0.2)
        OBSTACLE_AVOID_KPKD: tuple[float, float] = (0.8, 0.1)
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


_GLOBAL_CONFIG: Config = Config()


@export
def GLOBAL_CONFIG() -> Config:  # Function to use the decorator
    return _GLOBAL_CONFIG


@export
def load_configuration(path: str = "./piclient.toml") -> Config:
    """Load a TOML configuration file and hydrate the internal global :class:`Config` object.

    Each top-level key in the TOML file should correspond to a nested
    dataclass name inside :class:`Config` (e.g. ``CameraConfig``,
    ``ClientConfig``).  The values under that key are unpacked as keyword
    arguments to the dataclass constructor.

    :returns: :class:`Config`
    :raises: AttributeError if arguments are missing or do not match the type definition.
    """
    config: Config = GLOBAL_CONFIG()

    with open(path, "rb") as toml:
        raw_config: dict[str, Any] = load_toml(toml)

    for section_name, section_values in raw_config.items():
        if not hasattr(config, section_name):
            raise AttributeError(
                f"'{section_name}' is not an attribute of Config."
            )
        nested_cls: type = getattr(Config, section_name)
        if not isinstance(section_values, dict):
            raise AttributeError(
                f"TOML section '{section_name}' must be a table, "
                f"got {type(section_values).__name__} instead."
            )
        try:
            hydrated = nested_cls(**section_values)
        except TypeError as e:
            raise AttributeError(
                f"TOML section '{section_name}' does not match "
                f"the type definition. Check below for more details"
            ) from e
        setattr(config, section_name, hydrated)

    return config
