"""Parallel parking control for obstacle challenge.

The routine has two phases:
1. Follow the wall on the parking-lot side at a target normalized distance
   until the frontal ROI black ratio exceeds a threshold.
2. Execute a classic two-arc parking maneuver with configurable steering
   angles and durations.
"""

from collections.abc import Callable
from typing import Literal, Self
from time import perf_counter

from loguru import logger

from piclient.core.interface import DriveCommandExecutor
from piclient.core.lib import GLOBAL_CONFIG, PD, calculate_EMA, export
from piclient.core.vision import WallsAndObstacles

ParkingState = Literal["follow_wall_1", "align_with_corner", "follow_wall_2", "approach_lot", "arc_one", "arc_two", "parked"]
"""States used by :class:`ParallelParkingStateMachine`."""
ParkingSide = Literal["left", "right"]
"""Parking-lot side labels retained for API typing."""

_parking_cfg = GLOBAL_CONFIG().ParallelParkingConfig

@export
class ParallelParkingStateMachine:
    """State machine for wall-follow and two-arc parallel parking."""

    def __init__(
        self,
        drive_command_executor: DriveCommandExecutor,
        round_driving_direction: Literal["CLOCKWISE", "COUNTERCLOCKWISE"],
        drive_command_duration_s: float = GLOBAL_CONFIG(
        ).SharedChallengeConfig.DRIVE_COMMAND_DURATION,
        wall_follow_1_speed: float = _parking_cfg.WALL_FOLLOW_1_SPEED,
        wall_follow_1_kpkd: tuple[float, float] = _parking_cfg.WALL_FOLLOW_1_KPKD,
        wall_follow_1_offset_factor: float = _parking_cfg.WALL_FOLLOW_1_OFFSET_FACTOR,
        wall_follow_2_speed: float = _parking_cfg.WALL_FOLLOW_2_SPEED,
        wall_follow_2_offset_factor: float = _parking_cfg.WALL_FOLLOW_2_OFFSET_FACTOR,
        wall_follow_2_kpkd: tuple[float, float] = _parking_cfg.WALL_FOLLOW_2_KPKD,
        arc_one_servo_angle: float = _parking_cfg.ARC_ONE_SERVO_ANGLE,
        arc_two_servo_angle: float = _parking_cfg.ARC_TWO_SERVO_ANGLE,
        arc_one_duration_s: float = _parking_cfg.ARC_ONE_DURATION,
        arc_two_duration_s: float = _parking_cfg.ARC_TWO_DURATION,
        time_provider: Callable[[], float] = perf_counter,
    ) -> None:
        """Initialize wall-following and two-arc parking parameters.

        :param drive_command_executor: Command sink used for parking motion.
        :param round_driving_direction: Direction of the round driving, either "CLOCKWISE" or "COUNTERCLOCKWISE".
        :param drive_command_duration_s: Duration of regular wall-following
            commands in seconds.
        :param wall_follow_1_speed: Speed used while following the first wall.
        :param wall_follow_1_kpkd: Proportional and derivative wall-following
            gains for the first wall.
        :param wall_follow_1_offset_factor: Factor to adjust the wall-following offset for the first wall.
        :param wall_follow_2_speed: Speed used while following the second wall.
        :param wall_follow_2_offset_factor: Factor to adjust the wall-following offset for the second wall.
        :param wall_follow_2_kpkd: Proportional and derivative wall-following
            gains for the second wall.
        :param arc_one_servo_angle: Steering angle for the first arc.
        :param arc_two_servo_angle: Steering angle for the second arc.
        :param arc_one_duration_s: Duration of the first arc in seconds.
        :param arc_two_duration_s: Duration of the second arc in seconds.
        :returns: ``None``.
        :rtype: None
        """
        self.drive_command_executor = drive_command_executor
        self.drive_command_duration_s = drive_command_duration_s

        self.round_driving_direction = round_driving_direction

        self.wall_follow_1_speed = wall_follow_1_speed
        self.wall_follow_1_controller = PD(*wall_follow_1_kpkd)
        self.wall_follow_1_offset_factor = wall_follow_1_offset_factor
        self.wall_follow_2_speed = wall_follow_2_speed
        self.wall_follow_2_offset_factor = wall_follow_2_offset_factor
        self.wall_follow_2_controller = PD(*wall_follow_2_kpkd)

        self.arc_one_servo_angle: float = arc_one_servo_angle
        self.arc_two_servo_angle: float = arc_two_servo_angle
        self.arc_one_duration_s: float = arc_one_duration_s
        self.arc_two_duration_s: float = arc_two_duration_s
        self.time_provider = time_provider

        self.wall_follow_1_start_time_s: float | None = None
        self.align_with_corner_start_time_s: float | None = None
        self.arc_one_start_time_s: float | None = None
        self.arc_two_start_time_s: float | None = None
        self.approach_lot_start_time_s: float | None = None

        self.current_state: ParkingState = "follow_wall_1"
        self.parking_lot_error: float = 0.0
        self.previous_correction: float = 0
        self.parking_side: ParkingSide | None = None

    async def __aenter__(self) -> Self:
        """Enter the parking context and start command execution.

        :returns: This initialized parking state machine.
        :rtype: Self
        """
        await self.drive_command_executor.__aenter__()
        return self

    async def __aexit__(self, exc_type: type[BaseException], exc_value: BaseException, traceback: object) -> None:
        """Stop the underlying drive command executor.

        :param exc_type: Exception class raised in the context, or ``None``.
        :param exc_value: Exception instance raised in the context, or
            ``None``.
        :param traceback: Traceback for the context exception, or ``None``.
        :returns: ``None``.
        :rtype: None
        """
        await self.drive_command_executor.__aexit__(exc_type, exc_value, traceback)

    def update(self, walls_and_obstacles: WallsAndObstacles) -> None:
        """Update parking state and wall error from normalized marker data.

        A lone closer marker below ``y=0.6`` starts the approach phase. When
        both markers disappear for 2.5 seconds, the first reverse arc begins.
        Marker coordinates and bounding boxes are expected to be normalized by
        :class:`ParkingLot`.

        :param walls_and_obstacles: Latest wall, obstacle, and parking-marker
            measurements.
        """
        if self.current_state == "follow_wall_1" and self.wall_follow_1_start_time_s is None:
            self.wall_follow_1_start_time_s = self.time_provider()
        if self.current_state == "align_with_corner" and self.align_with_corner_start_time_s is None:
            self.align_with_corner_start_time_s = self.time_provider()
        self.walls_and_obstacles = walls_and_obstacles

        if (
            self.current_state == "follow_wall_1" 
            and self.round_driving_direction == "COUNTERCLOCKWISE"
        ):
            self.current_state = "follow_wall_2"
            self.wall_follow_1_start_time_s = float("inf")  # Prevent re-entry into this state
        elif (
            self.current_state == "follow_wall_1"
            and (
                self.walls_and_obstacles.parking_lot.closer is None
                or self.walls_and_obstacles.parking_lot.closer.y_centroid > 0.85
                or (self.wall_follow_1_start_time_s is not None
                    and self.time_provider() - self.wall_follow_1_start_time_s > 7.0)
            )
        ):
            self.current_state = "align_with_corner"
            self.wall_follow_1_start_time_s = float("inf")
        elif (
            self.current_state == "align_with_corner"
            and self.align_with_corner_start_time_s is not None
            and self.time_provider() - self.align_with_corner_start_time_s > 3.0
        ):
            self.current_state = "follow_wall_2"
            self.align_with_corner_start_time_s = float("inf")
        elif (
            self.walls_and_obstacles.parking_lot.further is None
            and self.walls_and_obstacles.parking_lot.closer is not None
            and self.walls_and_obstacles.parking_lot.closer.y_centroid > 0.6
            and self.current_state == "follow_wall_2"
        ):
            self.current_state = "approach_lot"
            self.approach_lot_start_time_s = self.time_provider()
        elif (
            self.walls_and_obstacles.parking_lot.closer is None
            and self.walls_and_obstacles.parking_lot.further is None
            and self.current_state == "approach_lot"
            and self.approach_lot_start_time_s is not None
            and self.time_provider() - self.approach_lot_start_time_s >= 1.75
        ):
            self.current_state = "arc_one"
            self.approach_lot_start_time_s = None

        if self.walls_and_obstacles.parking_lot.closer is None:
            self.parking_side = None
            self.parking_lot_error = 0.0
            return
        
        marker = self.walls_and_obstacles.parking_lot.closer
        marker_offset = marker.bbox[2] * self.wall_follow_1_offset_factor
        self.wall_follow_1_error = -((marker.x_centroid - 0.5) - marker_offset)

        active_wall = self.walls_and_obstacles.parking_lot.closer
        if (
            self.walls_and_obstacles.parking_lot.closer.bbox[0] <= 0.1
            or self.walls_and_obstacles.parking_lot.closer.bbox[0] + self.walls_and_obstacles.parking_lot.closer.bbox[2] >= 0.9
        ):
            # Parking lot clipping edge of frame, use the further contour if available
            if self.walls_and_obstacles.parking_lot.further is not None:
                active_wall = self.walls_and_obstacles.parking_lot.further

        normalized_x = (active_wall.x_centroid * 2.0) - 1.0
        wall_follow_2_offset = self.wall_follow_2_offset_factor * \
            active_wall.bbox[2]  # bbox[2] is the width of the bounding box

        if self.round_driving_direction == "CLOCKWISE":
            self.parking_lot_error = -normalized_x - wall_follow_2_offset
        else:
            self.parking_lot_error = -normalized_x + wall_follow_2_offset

    def _handle_follow_wall_1(self) -> None:
        """Handle the first wall-following state.

        This method computes the necessary correction based on the current wall distance and submits a drive command to the executor."""
        correction = calculate_EMA(self.wall_follow_1_controller.tick(
            self.wall_follow_1_error), self.previous_correction, 0.8)
        self.previous_correction = correction

        self.drive_command_executor.submit(
            self.wall_follow_1_speed, correction * 90 + 90, self.drive_command_duration_s)
        logger.debug(
            f"Wall-following: speed={self.wall_follow_1_speed}, correction={correction:.2f}, servo_angle={correction * 90 + 90:.2f}")

    def _handle_align_with_corner(self) -> None:
        """Handle the align-with-corner state.

        This method performs a 90 degree turn to align the vehicle parallel to the parking lot, preparing for the second wall-following phase."""

        self.drive_command_executor.submit(
            -0.3 , 150, self.drive_command_duration_s) 

    def _handle_follow_wall_2(self) -> None:
        """Handle the wall-following state.

        This method computes the necessary correction based on the current wall distance and submits a drive command to the executor."""
        correction = calculate_EMA(self.wall_follow_2_controller.tick(
            self.parking_lot_error), self.previous_correction, 0.35)
        self.previous_correction = correction

        self.drive_command_executor.submit(
            self.wall_follow_2_speed, correction * 90 + 90, self.drive_command_duration_s)
        logger.debug(
            f"Wall-following: speed={self.wall_follow_2_speed}, correction={correction:.2f}, servo_angle={correction * 90 + 90:.2f}")

    def _handle_approach_lot(self) -> None:
        """Handle the approach-lot state.

        This method drives the vehicle straight forwards until the parking lot Y centroid exceeds a threshold,
        indicating that the vehicle is close enough to the parking lot to begin the parking maneuver."""
        self.drive_command_executor.submit(
            self.wall_follow_2_speed, 90, self.drive_command_duration_s)  # Slight steering trim

    def _handle_arc(self, servo_angle: float, duration_s: float) -> None:
        """Drive a reverse arc and advance to the next parking phase.

        Steering is mirrored for clockwise travel. On completion of the second
        arc, the state becomes ``"parked"`` and a near-zero-speed command is
        submitted.
        """
        servo_angle = servo_angle if self.round_driving_direction == "COUNTERCLOCKWISE" else 180 - servo_angle
        if self.current_state == "arc_one" and self.arc_one_start_time_s is None:
            self.arc_one_start_time_s = self.time_provider()
        elif self.current_state == "arc_two" and self.arc_two_start_time_s is None:
            self.arc_two_start_time_s = self.time_provider()

        start_time = self.arc_one_start_time_s if self.current_state == "arc_one" else self.arc_two_start_time_s
        if start_time is None:
            return

        elapsed = self.time_provider() - start_time
        if elapsed >= duration_s:
            if self.current_state == "arc_one":
                self.current_state = "arc_two"
                self.arc_one_start_time_s = None
            else:
                self.current_state = "parked"
                self.arc_two_start_time_s = None
                self.drive_command_executor.submit(
                    0.01, 90, self.drive_command_duration_s)  # Stop the vehicle
            return

        self.drive_command_executor.submit(
            _parking_cfg.ARC_SPEED, servo_angle, self.drive_command_duration_s)
        logger.debug(
            f"Executing reverse arc: state={self.current_state}, "
            f"speed={_parking_cfg.ARC_SPEED}, servo_angle={servo_angle}, "
            f"elapsed={elapsed:.2f}s/{duration_s:.2f}s"
        )

    def _handle_arc_one(self) -> None:
        """Drive backwards in the first fixed-angle arc."""
        self._handle_arc(self.arc_one_servo_angle, self.arc_one_duration_s)

    def _handle_arc_two(self) -> None:
        """Drive backwards in the second fixed-angle arc and then stop."""
        self._handle_arc(self.arc_two_servo_angle, self.arc_two_duration_s)

    def handle_state_actions(self) -> bool:
        """Submit the command for the current parking state.

        State data must already have been supplied through :meth:`update`.
        Returns ``True`` only after the state reaches ``"parked"``.

        :returns: Whether the parking routine is complete.
        """
        if self.current_state == "follow_wall_1":
            self._handle_follow_wall_1()
        elif self.current_state == "align_with_corner":
            self._handle_align_with_corner()
        elif self.current_state == "follow_wall_2":
            self._handle_follow_wall_2()
        elif self.current_state == "approach_lot":
            self._handle_approach_lot()
        elif self.current_state == "arc_one":
            self._handle_arc_one()
        elif self.current_state == "arc_two":
            self._handle_arc_two()
        elif self.current_state == "parked":
            return True
        return False
