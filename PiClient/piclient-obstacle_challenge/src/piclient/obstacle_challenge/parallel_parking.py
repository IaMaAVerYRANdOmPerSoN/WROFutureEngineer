"""Parallel parking control for obstacle challenge.

The routine has two phases:
1. Follow the wall on the parking-lot side at a target normalized distance
   until the frontal ROI black ratio exceeds a threshold.
2. Execute a classic two-arc parking maneuver with configurable steering
   angles and durations.
"""

from typing import Literal, Self

from loguru import logger
from piclient.core.interface import DriveCommandExecutor
from piclient.core.lib import GLOBAL_CONFIG, PD
from piclient.core.vision import WallsAndObstacles

ParkingState = Literal["follow_wall", "arc_one", "arc_two", "parked"]
ParkingSide = Literal["left", "right"]

_parking_cfg = GLOBAL_CONFIG().ParallelParkingConfig
_client_cfg = GLOBAL_CONFIG().ClientConfig


class ParallelParkingStateMachine:
    """State machine for wall-follow and two-arc parallel parking."""
    
    def __init__(
        self,
        drive_command_executor: DriveCommandExecutor,
        drive_command_duration_s: float = GLOBAL_CONFIG().SharedChallengeConfig.DRIVE_COMMAND_DURATION,
        wall_follow_speed: float = _parking_cfg.WALL_FOLLOW_SPEED,
        wall_follow_target_distance: float = _parking_cfg.WALL_FOLLOW_TARGET_DISTANCE,
        wall_follow_kpkd: tuple[float, float] = _parking_cfg.WALL_FOLLOW_KPKD,
        arc_one_servo_angle: float = _parking_cfg.ARC_ONE_SERVO_ANGLE,
        arc_two_servo_angle: float = _parking_cfg.ARC_TWO_SERVO_ANGLE,
        arc_one_duration_s: float = _parking_cfg.ARC_ONE_DURATION,
        arc_two_duration_s: float = _parking_cfg.ARC_TWO_DURATION,
    ) -> None:
        """Initialize wall-following and two-arc parking parameters.

        :param drive_command_executor: Command sink used for parking motion.
        :param drive_command_duration_s: Duration of regular wall-following
            commands in seconds.
        :param wall_follow_speed: Speed used while approaching the lot.
        :param wall_follow_target_distance: Desired normalized wall distance.
        :param wall_follow_kpkd: Proportional and derivative wall-following
            gains.
        :param arc_one_servo_angle: Steering angle for the first arc.
        :param arc_two_servo_angle: Steering angle for the second arc.
        :param arc_one_duration_s: Duration of the first arc in seconds.
        :param arc_two_duration_s: Duration of the second arc in seconds.
        :returns: ``None``.
        :rtype: None
        """
        self.drive_command_executor = drive_command_executor
        self.drive_command_duration_s = drive_command_duration_s

        self.wall_follow_speed = wall_follow_speed
        self.wall_follow_target_distance = wall_follow_target_distance
        self.wall_follow_controller = PD(*wall_follow_kpkd)

        self.arc_one_servo_angle: float = arc_one_servo_angle
        self.arc_two_servo_angle: float = arc_two_servo_angle
        self.arc_one_duration_s: float = arc_one_duration_s
        self.arc_two_duration_s: float = arc_two_duration_s

        self.arc_one_start_time_s: float | None = None
        self.arc_two_start_time_s: float | None = None

        self.current_state: ParkingState = "follow_wall"
        self.parking_side: ParkingSide | None = None
        self.walls_and_obstacles: WallsAndObstacles | None = None
        self.wall_distance: float | None = None

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
        """Update the state machine based on the latest vision data.

        :param walls_and_obstacles: The latest vision data containing wall and obstacle information.
        """
        self.walls_and_obstacles = walls_and_obstacles

        if walls_and_obstacles.parking_lot.closer is not None:
            self.parking_side = "left" if walls_and_obstacles.parking_lot.closer.x_centroid < 0.5 else "right"
            self.wall_distance = walls_and_obstacles.walls.left if self.parking_side == "left" else walls_and_obstacles.walls.right
        else:
            self.parking_side = None
            self.wall_distance = self.wall_follow_target_distance

        logger.debug(f"Updated state machine:\nparking_side={self.parking_side},\nwall_distance={self.wall_distance},\nwalls_and_obstacles={self.walls_and_obstacles}")

    def _handle_follow_wall(self) -> None:
        """Handle the wall-following state.

        This method computes the necessary correction based on the current wall distance and submits a drive command to the executor."""
        if self.wall_distance is None:
            raise ValueError("Wall distance is not set. Ensure that update() has been called with valid vision data.")
        correction = self.wall_follow_controller.tick(self.wall_distance, self.wall_follow_target_distance)
        self.drive_command_executor.submit(self.wall_follow_speed, correction * 90 + 90, self.drive_command_duration_s)

    def handle_state_actions(self) -> bool:
        """Handle actions for the current state.

        :param walls_and_obstacles: The latest vision data containing wall and obstacle information.
        :return: True if the parking routine is finished, False otherwise.
        """
        if self.current_state == "follow_wall":
            self._handle_follow_wall()
        return False