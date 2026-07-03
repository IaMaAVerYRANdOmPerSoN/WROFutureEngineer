"""Centralised configuration for the Pi Client.

Contains nested dataclasses for camera, serial client, vision processing,
and challenge-specific tuning parameters.
"""
# File is too long, will most likely move defaults elseware and create a abstract config class,
# and a runtime config class that inherits from the abstract config class and adds the ability to load from toml/env/cli args
from dataclasses import dataclass, field, is_dataclass
from typing import Any, Literal, Self, get_origin
from collections.abc import Callable
from inspect import get_annotations
import ast
import numpy as np
from .exporter import export
from os import environ

from tomllib import load as load_toml


class Freezeable:
    """Base class that can be frozen to prevent mutation."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._frozen = False  # Flag to indicate if the dataclass is frozen
        super().__init__(*args, **kwargs)

    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "_frozen", False) and name != "_frozen":
            raise AttributeError(
                f"{type(self).__name__} is frozen and cannot be modified.")
        super().__setattr__(name, value)

    def freeze(self) -> None:
        """Freeze the class to prevent further modifications."""
        self._frozen = True
        for _, attr in vars(self).items():
            if isinstance(attr, Freezeable):
                attr.freeze()


@export
class Config(Freezeable):
    """Root configuration container.

    All configuration is organised into nested :class:`dataclass` subclasses.
    Each subclass is instantiated at construction time.

    Usage:

    .. code-block:: python

        >>> from piclient.core.lib import GLOBAL_CONFIG
        >>> cfg = GLOBAL_CONFIG()
        >>> cfg.CameraConfig.OUTPUT_WIDTH
        512
        >>> cfg.OpenChallengeConfig.WALL_FOLLOW_KPKD
        (0.5, 0.0)

    Override by priority (highest first):
        1. CLI flags:     ``wro --CameraConfig.OUTPUT_WIDTH 640``
        2. Environment:   ``WRO_CAMERACONFIG_OUTPUT_WIDTH=640``
        3. Code defaults:  dataclass field values below

    Load an arbitrary TOML file at runtime:

    .. code-block:: python

        >>> cfg = GLOBAL_CONFIG().from_toml("my_config.toml")
        >>> cfg.CameraConfig.OUTPUT_WIDTH
        640

    Where ``my_config.toml`` contains::

        [CameraConfig]
        OUTPUT_WIDTH = 640

    Freeze after init to prevent accidental mutation:

    .. code-block:: python

        >>> cfg.freeze()
        >>> cfg.CameraConfig.OUTPUT_WIDTH = 999  # AttributeError
    """

    # Primative type casters for environment variable parsing and CLI argument parsing.
    casters: dict[type, Callable[[str], object]] = {
        int: int,
        float: float,
        str: str,
        bool: lambda x: x.lower() in ("true", "1", "yes"),
        tuple: ast.literal_eval,
        dict: ast.literal_eval,
        type(None): lambda _: None,
    }

    # ndarray casters
    for _dt in (np.uint8, np.uint16, np.uint32, np.uint64, np.float32, np.float64):
        casters[np.ndarray[tuple[int, ...], np.dtype[_dt]]] = (
            lambda raw, dt=_dt: np.array(ast.literal_eval(raw), dtype=dt)
        )

    # Fucking hate Literals
    casters[Literal] = lambda x: x  # type: ignore

    def __init__(self) -> None:
        """Initialise the configuration with nested dataclasses."""
        for name in dir(type(self)):
            if name.startswith("_"):
                continue
            cls: type | None = getattr(type(self), name, None)
            if is_dataclass(cls):
                setattr(self, name, cls())

        super().__init__()  # Call Freezeable.__init__ to set _frozen flag

    def __repr__(self) -> str:
        lines: list[str] = []
        for name in dir(type(self)):
            if name.startswith("_"):
                continue
            cls: type | None = getattr(type(self), name, None)
            if is_dataclass(cls):
                lines.append(f"{name}: {getattr(self, name)}")
        return "\n".join(lines)

    def _get_nested_attr(self, path: str, sep: str = ".") -> Any:
        """Get ``self<sep>a<sep>b<sep>c`` given ``path == 'a<sep>b<sep>c'``."""
        root = self
        for part in path.split(sep):
            root = getattr(root, part)
        return root

    def set_nested_attr(self, path: str, value: object, sep: str = ".") -> None:
        """Set ``self<sep>a<sep>b<sep>c = value`` given ``path == 'a<sep>b<sep>c'``."""
        *parents, leaf = path.split(sep)
        root: object = self._get_nested_attr(sep.join(parents), sep)
        setattr(root, leaf, value) if hasattr(
            root, leaf) else None  # Only set if attribute exists

    def get_annotation(self, path: str, sep: str = ".") -> type:
        """Get the type annotation of ``self<sep>a<sep>b<sep>c`` given ``path == 'a<sep>b<sep>c'``."""
        *parents, leaf = path.split(sep)
        root = self._get_nested_attr(sep.join(parents), sep)
        annotation = get_annotations(type(root)).get(leaf, None)
        if annotation is None:
            raise TypeError(
                f"No type annotation found for path '{path}'."
                "If you have not extended the Config class, This is most likely an internal error."
                "Please report this issue to the developers."
                "If you have extended the Config class, please ensure that you have added a type annotation for this attribute."
            )
        return annotation

    @classmethod
    def get_caster(cls, type_: type) -> Callable[[str], object]:
        origin: type = get_origin(type_) or type_
        caster: Callable[[str], object] | None = cls.casters.get(
            type_) or cls.casters.get(origin)
        if caster is None:
            raise TypeError(
                f"No caster found for type '{type_}'."
                "If you have not extended the Config class, This is most likely an internal error."
                "Please report this issue to the developers."
                "If you have extended the Config class, please ensure that you have registered a caster for this type in the 'Config.casters' dictionary."
            )
        return caster

    def from_toml(self, path: str = "./piclient.toml") -> Self:
        """Load a TOML configuration file and hydrate the internal global :class:`Config` object.

        Each top-level key in the TOML file should correspond to a nested
        dataclass name inside :class:`Config` (e.g. ``CameraConfig``,
        ``ClientConfig``).  The values under that key are unpacked as keyword
        arguments to the dataclass constructor.

        :returns: :class:`Config`
        :raises: AttributeError if arguments are missing or do not match the type definition.
        """

        with open(path, "rb") as toml:
            raw_config: dict[str, Any] = load_toml(toml)

        for section_name, section_values in raw_config.items():
            if not hasattr(self, section_name):
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
            setattr(self, section_name, hydrated)

        return self

    def from_env(self) -> Self:
        """Load configuration from environment variables.

        Environment variable names should be in the format
        ``WRO__<K1>__<K2>__<K3> ... __<Ki>`` (note double underscores), where ``<Kn>``
        corresponds to the nth-level nested attribute in the :class:`Config`
        dataclass tree (underscores replace dots).

        :returns: :class:`Config`
        """
        conversion_map: dict[str, str] = {
            "GENERALCONFIG": "GeneralConfig",
            "CAMERACONFIG": "CameraConfig",
            "CLIENTCONFIG": "ClientConfig",
            "VISIONCONFIG": "VisionConfig",
            "OPENCHALLENGECONFIG": "OpenChallengeConfig",
            "OBSTACLECHALLENGECONFIG": "ObstacleChallengeConfig",
            "LIDARCONFIG": "LiDARConfig",
        }

        prefix = "WRO__"
        for env_key, env_value in environ.items():
            if not env_key.startswith(prefix):
                continue

            path = env_key[len(prefix):]
            path = conversion_map[path.split("__")[0]] + "__" + "__".join(
                path.split("__")[1:]) if len(path.split("__")) > 1 else conversion_map[path]
            annotation = self.get_annotation(path, sep="__")
            caster = type(self).get_caster(annotation)

            self.set_nested_attr(path, caster(env_value), sep="__")
        return self

    @dataclass
    class GeneralConfig(Freezeable):
        """
        General Configuration.

        Controls logging level and which challenge to run.
        """
        LEVEL: Literal["CRITICAL", "ERROR", "WARNING",
                       "SUCCESS", "INFO", "DEBUG"] = "WARNING"
        CHALLENGE: Literal["open", "obstacle"] = "open"

    @dataclass
    class CameraConfig(Freezeable):
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
    class ClientConfig(Freezeable):
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
    class VisionConfig(Freezeable):
        """Vision processing parameters.

        Includes the perspective-transform homography matrix, HSV colour
        thresholds for wall/line detection, and region-of-interest slices.
        """
        PERSPECTIVE_TRANSFORM: np.ndarray[tuple[int, ...], np.dtype[np.float32]] = field(default_factory=lambda: np.array([
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
    class OpenChallengeConfig(Freezeable):
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
    class ObstacleChallengeConfig(Freezeable):
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
    class LiDARConfig(Freezeable):
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
