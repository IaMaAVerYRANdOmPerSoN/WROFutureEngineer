"""Centralised configuration for the Pi Client.

Contains nested dataclasses for camera, serial client, vision processing,
and challenge-specific tuning parameters.
"""
# TODO: File is too long, will most likely move defaults elseware and create a abstract config class,
# and a runtime config class that inherits from the abstract config class and adds the ability to load from toml/env/cli args

from typing import Any, Literal, Self, get_origin

import ast
from dataclasses import dataclass, field, is_dataclass
from collections.abc import Callable
from inspect import get_annotations
from tomllib import load as load_toml
from os import environ

import numpy as np

from .exporter import export


def _slice_length(axis: slice, total: int) -> int:
    """Return the number of elements selected by a one-dimensional slice.

    This helper is used when converting camera ROI definitions into concrete
    dimensions. It normalizes missing slice bounds against the full dimension size
    so that slices such as ``slice(None, None, None)`` or partial windows resolve
    to real element counts.

    :param axis: A :class:`slice` describing the inclusive start and exclusive
        stop for the desired interval. The value is normalized against *total*
        when either bound is ``None``.
    :param total: The full size of the axis being sliced, used when the slice
        omits either bound.
    :returns: The number of elements in the selected region.
    :rtype: int
    """
    start = 0 if axis.start is None else axis.start
    stop = total if axis.stop is None else axis.stop
    return stop - start


@export
class Freezeable:
    """Base class that can prevent mutation after configuration is complete.

    Instances remain mutable until :meth:`freeze` is called. Freezing also
    traverses nested containers so that contained :class:`Freezeable`
    instances become immutable with the parent.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize a mutable instance with its freeze guard disabled.

        Positional and keyword arguments are forwarded to the next class in
        the method-resolution order after ``_frozen`` is initialized. This
        allows the class to be used with dataclasses and other cooperative
        base classes.

        :param args: Positional arguments forwarded to the cooperative base
            initializer.
        :param kwargs: Keyword arguments forwarded to the cooperative base
            initializer.
        :returns: ``None``.
        :rtype: None
        """
        # Flag to indicate if the dataclass is frozen
        super().__setattr__("_frozen", False)
        super().__init__(*args, **kwargs)

    def __setattr__(self, name: str, value: Any) -> None:
        """Assign an attribute unless this instance has been frozen.

        :param name: Attribute name to assign.
        :param value: New value for the attribute.
        :raises AttributeError: If :meth:`freeze` has already been called on
            this instance.
        :returns: ``None``.
        :rtype: None
        """
        if getattr(self, "_frozen", False):
            raise AttributeError(
                f"{type(self).__name__} is frozen and cannot be modified.")
        super().__setattr__(name, value)

    def freeze(self) -> None:
        """Freeze this object and every nested :class:`Freezeable` object.

        After this method returns, assignments to attributes on this object or
        recursively contained ``Freezeable`` instances raise
        :class:`AttributeError`.

        :returns: ``None``.
        :rtype: None
        """
        super().__setattr__("_frozen", True) # Allow calling freeze() multiple times without error
        for _, value in vars(self).items():
            self._freeze_recursively(value)

    def _freeze_recursively(self, obj: Any = None) -> None:
        """Recursively freeze nested freezeable values in a container.

            :param obj: Value to inspect. Nested :class:`Freezeable` instances and
            values inside lists, tuples, sets, and dictionaries are visited.
        :returns: ``None``.
        :rtype: None
        """
        if isinstance(obj, Freezeable):
            obj.freeze()
        elif isinstance(obj, (list, tuple, set)):
            for item in obj:  # pyright: ignore[reportUnknownVariableType]
                self._freeze_recursively(item)
        elif isinstance(obj, dict):
            for key, val in obj.items(): # pyright: ignore[reportUnknownVariableType]
                self._freeze_recursively(key)
                self._freeze_recursively(val)


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

    casters[np.ndarray] = lambda raw: np.array(ast.literal_eval(raw))

    # Fucking hate Literals
    casters[Literal] = lambda x: x  # type: ignore

    def __init__(self) -> None:
        """Create each dataclass-defined configuration section.

        Public dataclass subclasses declared on the concrete configuration
        class are instantiated and attached as attributes. The inherited
        freeze guard is then initialized in its mutable state.

        :returns: ``None``.
        :rtype: None
        """
        for name in dir(type(self)):
            if name.startswith("_"):
                continue
            cls: type | None = getattr(type(self), name, None)
            if is_dataclass(cls):
                setattr(self, name, cls())

        super().__init__()  # Call Freezeable.__init__ to set _frozen flag

    def __repr__(self) -> str:
        """Return a readable listing of every configured dataclass section.

        Each public nested dataclass is rendered on its own line using its
        normal representation. This is intended for diagnostics and logs, not
        for serialization or round-tripping configuration values.

        :returns: Newline-separated section names and values.
        :rtype: str
        """
        lines: list[str] = []
        for name in dir(type(self)):
            if name.startswith("_"):
                continue
            cls: type | None = getattr(type(self), name, None)
            if is_dataclass(cls):
                lines.append(f"{name}: {getattr(self, name)}")
        return "\n".join(lines)

    def _get_nested_attr(self, path: str, sep: str = ".") -> Any:
        """Resolve a nested configuration attribute from a dotted path.

        :param path: Attribute path relative to this configuration object.
        :param sep: Separator between path components; defaults to ``.``.
        :returns: The value stored at the nested path.
        :raises AttributeError: If any path component is absent.
        """
        root = self
        for part in path.split(sep):
            root = getattr(root, part)
        return root

    def set_nested_attr(self, path: str, value: object, sep: str = ".") -> None:
        """Set an existing nested configuration attribute from a path.

        Unknown leaf attributes are ignored so command-line arguments can be
        filtered against the configuration shape without creating new state.

        :param path: Attribute path relative to this configuration object.
        :param value: Replacement value for the existing leaf attribute.
        :param sep: Separator between path components; defaults to ``.``.
        :returns: ``None``.
        :rtype: None
        :raises AttributeError: If a parent path component is absent.
        """
        *parents, leaf = path.split(sep)
        root: object = self._get_nested_attr(sep.join(parents), sep)
        setattr(root, leaf, value) if hasattr(
            root, leaf) else None  # Only set if attribute exists

    def get_annotation(self, path: str, sep: str = ".") -> type:
        """Return the declared type of a nested configuration attribute.

        :param path: Attribute path relative to this configuration object.
        :param sep: Separator between path components; defaults to ``.``.
        :returns: Runtime type annotation for the leaf attribute.
        :rtype: type
        :raises AttributeError: If a parent path component is absent.
        :raises TypeError: If the leaf has no type annotation.
        """
        *parents, leaf = path.split(sep)
        root: object = self._get_nested_attr(sep.join(parents), sep)
        annotation = get_annotations(type(root)).get(leaf, None)
        if annotation is None:
            raise TypeError(
                f"No type annotation found for path '{path}'. "
                "If you have not extended the Config class, This is most likely an internal error; "
                "Please report this issue to the developers. "
                "If you have extended the Config class, please ensure that you have added a type annotation for this attribute."
            )
        return annotation

    @classmethod
    def get_caster(cls, type_: type) -> Callable[[str], object]:
        """Find the string-to-value caster registered for a configuration type.

        Generic aliases are reduced to their origin before lookup, allowing
        callers to use annotations such as ``tuple[...]`` or ``dict[...]``.

        :param type_: Type annotation whose textual input must be converted.
        :returns: Callable that converts one string into the requested type.
        :rtype: collections.abc.Callable[[str], object]
        :raises TypeError: If no caster is registered for *type_*.
        """
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
        """Populate this configuration object from a TOML file.

        The TOML file is expected to contain one table per nested dataclass section,
        such as ``CameraConfig`` or ``ClientConfig``. Each table is unpacked as
        keyword arguments to the corresponding dataclass constructor and then
        assigned onto the live :class:`Config` instance.

        :param path: Filesystem path to the TOML configuration file to parse.
        :returns: This same :class:`Config` instance after the values have been
            hydrated.
        :rtype: Config
        :raises AttributeError: If a table name does not exist on the config or if
            the values do not match the dataclass definition.
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
        """Hydrate this configuration object from environment variables.

        Variables are expected to follow the ``WRO__<SECTION>__<KEY>`` convention,
        where each nested component corresponds to a dataclass section and field in
        the :class:`Config` tree. The values are converted using the registered
        caster for their declared type before being assigned to the matching
        nested attributes.

        :returns: This same :class:`Config` instance after applying environment
            overrides.
        :rtype: Config
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
            path = conversion_map[path.split("__")[0].upper()] + "__" + "__".join(
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
                       "SUCCESS", "INFO", "DEBUG"] = "SUCCESS"
        CHALLENGE: Literal["open", "obstacle"] = "open"

    @dataclass
    class CameraConfig(Freezeable):
        """Camera hardware and frame-capture settings.

        Controls picamera2 format, resolution, thread pool size,
        timeouts, sensor/control parameters, and the initial crop ROI.
        """
        FORMAT: dict[str, Any] = field(default_factory=lambda: {
            "format": "BGR888",
            # Camera API expects (width, height); NumPy/OpenCV arrays usually use (height, width).
            "size": (512, 384)
        })
        INITIAL_ROI: tuple[slice, slice, slice] = np.s_[
            384 // 5: 384 - 384 // 8, :, :]
        OUTPUT_WIDTH: int = 512
        OUTPUT_HEIGHT: int = 384
        OUTPUT_CHANNELS: int = 3
        OUTPUT_SHAPE: tuple[int, int, int] = (
            OUTPUT_HEIGHT, OUTPUT_WIDTH, OUTPUT_CHANNELS)
        SHM_SIZE: int = OUTPUT_WIDTH * OUTPUT_HEIGHT * OUTPUT_CHANNELS
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
            "FrameDurationLimits": (16000, 16000),  # 62.5 FPS
            "AeEnable": True,  # Enables automatic exposure
        })
        FPS: float = None  # pyright: ignore[reportAssignmentType]

        def __post_init__(self):
            """Derive output dimensions, shared-memory size, and camera FPS.

            The derived values reflect the configured capture format and initial
            ROI, ensuring consumers use the cropped frame dimensions rather
            than stale defaults.

            :returns: ``None``.
            :rtype: None
            """
            object.__setattr__(self, "OUTPUT_WIDTH", _slice_length(
                self.INITIAL_ROI[1], self.FORMAT["size"][0]))
            object.__setattr__(self, "OUTPUT_HEIGHT", _slice_length(
                self.INITIAL_ROI[0], self.FORMAT["size"][1]))
            object.__setattr__(self, "OUTPUT_SHAPE", (
                self.OUTPUT_HEIGHT, self.OUTPUT_WIDTH, self.OUTPUT_CHANNELS))
            object.__setattr__(self, "SHM_SIZE", self.OUTPUT_WIDTH *
                               self.OUTPUT_HEIGHT * self.OUTPUT_CHANNELS)
            # Convert microseconds to seconds
            object.__setattr__(
                self, "FPS", 1 / (self.CONTROLS_CONFIG["FrameDurationLimits"][0] * 1e-6))

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
        SERVO_MIN_ANGLE: int = 30
        SERVO_MAX_ANGLE: int = 150
        SERVO_TRIM: int = 8

    @dataclass
    class VisionConfig(Freezeable):
        """Vision processing parameters.

        Includes the perspective-transform homography matrix, HSV colour
        thresholds for wall/line detection, and region-of-interest slices.
        """
        PERSPECTIVE_TRANSFORM: np.ndarray[tuple[int, int], np.dtype[np.float32]] = field(default_factory=lambda: np.array([
            [1, 0, 0],
            [0, 1, 0],
            [0, 0, 1]
        ], dtype=np.float32))  # Homography matrix

        LOWER_BLACK: tuple[int, int, int] = (0, 0, 0)
        UPPER_BLACK: tuple[int, int, int] = (179, 255, 70)

        # 384 // 5 = 76
        # 384 - 384 // 8 = 336
        # 336 - 76 = 260

        LEFT_WALL_ROI: tuple[slice, slice] = np.s_[
            260 // 5: 260 - 260 // 5, :512 // 3]  # // 5, 5, 5 original
        RIGHT_WALL_ROI: tuple[slice, slice] = np.s_[
            260 // 5: 260 - 260 // 5, 512 - 512 // 3:]
        CENTER_WALL_ROI: tuple[slice, slice] = np.s_[
            : 260//12, 512 // 2 - 512 // 10: 512 // 2 + 512 // 10]

        # Placeholder HSV thresholds for obstacles
        LOWER_RED_OBSTACLE: np.ndarray[tuple[int], np.dtype[np.uint8]] = field(
            default_factory=lambda: np.array([113, 162, 90], dtype=np.uint8))
        UPPER_RED_OBSTACLE: np.ndarray[tuple[int], np.dtype[np.uint8]] = field(
            default_factory=lambda: np.array([126, 255, 183], dtype=np.uint8))
        LOWER_GREEN_OBSTACLE: np.ndarray[tuple[int], np.dtype[np.uint8]] = field(
            default_factory=lambda: np.array([36, 100, 100], dtype=np.uint8))
        UPPER_GREEN_OBSTACLE: np.ndarray[tuple[int], np.dtype[np.uint8]] = field(
            default_factory=lambda: np.array([57, 255, 180], dtype=np.uint8))
        LOWER_YELLOW_OBSTACLE: np.ndarray[tuple[int], np.dtype[np.uint8]] = field(
            default_factory=lambda: np.array([87, 78, 121], dtype=np.uint8)
        )
        UPPER_YELLOW_OBSTACLE: np.ndarray[tuple[int], np.dtype[np.uint8]] = field(
            default_factory=lambda: np.array([96, 255, 239], dtype=np.uint8)
        )
        OBSTACLE_ROI: tuple[slice, slice] = np.s_[
            None: None, None: None]  # Everything

        LOWER_PARKING_LOT: np.ndarray[tuple[int], np.dtype[np.uint8]] = field(
            default_factory=lambda: np.array([152, 90, 84], dtype=np.uint8))
        UPPER_PARKING_LOT: np.ndarray[tuple[int], np.dtype[np.uint8]] = field(
            default_factory=lambda: np.array([175, 193, 236], dtype=np.uint8))

    @dataclass
    class SharedChallengeConfig(Freezeable):
        """Shared tuning parameters for both challenges.

        Includes PD gains, speeds, hysteresis thresholds, shared memory
        settings, and lap-length constants.
        """
        SHM_NAME: str = "camera_frame"
        DRIVE_COMMAND_DURATION: float = 0.2
        LAP_LENGTH_IN_TURNS: int = 4*3  # 4 turns per lap, 3 laps total
        TURN_DURATION: float = 3
        HYSTERESIS: int = 4  # Number of frames deciding before changing states
        TURN_COOLDOWN: float = 3.5  # How long it needs to take
        TURN_DETECTION_THRESHOLD: float = 0.12  # used to be 0.1
        # Amount of fill needed for a turn to be counted
        CENTER_FILL_THRESHOLD: float = 0.65

    @dataclass
    class OpenChallengeConfig(Freezeable):
        """Tuning parameters for the Open Challenge.
        Includes PD gains, speeds, hysteresis thresholds, shared memory
        settings, and lap-length constants.
        """
        WALL_FOLLOW_KPKD: tuple[float, float] = (1.0, 0.4)
        CORNER_TURN_KPKD: tuple[float, float] = (1.8, 0.2)
        STRAIGHT_SPEED: float = 0.42
        TURN_SPEED: float = 0.42

    @dataclass
    class ParallelParkingConfig(Freezeable):
        """Tuning values for the end-of-challenge parallel parking maneuver."""
        MIN_ENTRY_Y: float = 0.5
        WALL_FOLLOW_OFFSET_FACTOR: float = 2.75
        WALL_FOLLOW_KPKD: tuple[float, float] = (1.2, 0.2)
        WALL_FOLLOW_SPEED: float = 0.3
        FRONTAL_BLACK_RATIO_THRESHOLD: float = 0.7
        ARC_SPEED: float = -0.25
        ARC_ONE_SERVO_ANGLE: float = 30.0
        ARC_ONE_DURATION: float = 7
        ARC_TWO_SERVO_ANGLE: float = 150.0
        ARC_TWO_DURATION: float = 7

    @dataclass
    class ObstacleChallengeConfig(Freezeable):
        """Tuning parameters for the Obstacle Challenge.

        Includes PD gains for wall-following, corner turning, and obstacle
        avoidance, along with speeds and shared memory settings.
        """
        WALL_FOLLOW_KPKD: tuple[float, float] = (0.6, 0.35)
        CORNER_TURN_KPKD: tuple[float, float] = (0.65, 0.25)
        OBSTACLE_AVOID_KPKD: tuple[float, float] = (0.6, 0.35)
        STRAIGHT_SPEED: float = 0.4
        TURN_SPEED: float = 0.4
        OBSTACLE_AVOID_SPEED: float = 0.4
        OBSTACLE_BASE_OFFSET: float = 0 # Base offset in pixels to avoid the obstacle
        OBSTACLE_OFFSET_SCALING_FACTOR: float = 3 # Scaling factor * width of obstacle to account for distance changes

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
    """Return the process-wide mutable :class:`Config` singleton.

    The returned object is shared by all callers, so changing a nested value
    changes the configuration observed by subsequent consumers. Callers may
    invoke :meth:`Config.freeze` after applying overrides to prevent further
    mutation.

    :returns: The process-wide configuration instance.
    :rtype: Config
    """
    return _GLOBAL_CONFIG
