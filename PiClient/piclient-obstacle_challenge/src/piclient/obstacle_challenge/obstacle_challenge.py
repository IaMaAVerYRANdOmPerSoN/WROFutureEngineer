"""
Obstacle Challenge main loop class
Extends StateMachine to implement the main loop for the Obstacle Challenge.
"""
from collections.abc import Callable
from typing import Literal

from time import perf_counter

from numpy import isfinite
from loguru import logger

from piclient.core.interface import DriveCommandExecutor
from piclient.core.lib import PD, StateMachine, GLOBAL_CONFIG, calculate_EMA
from piclient.core.vision import WallsAndObstacles

from .transition_determinants import (
    TypedTranisitionManager,
    ChallengeState,
    Target,
    LapCount,
)
from .parallel_parking import ParallelParkingStateMachine


def get_wall_error(walls_and_obstacles: WallsAndObstacles) -> float:
    """Return the wall-following error as a finite scalar."""
    left_distance = float(walls_and_obstacles.walls.left)
    right_distance = float(walls_and_obstacles.walls.right)

    if not isfinite(left_distance):
        left_distance = 1.0
    if not isfinite(right_distance):
        right_distance = 1.0

    return right_distance - left_distance


class ObstacleChallengeStateMachine(StateMachine[
    [],
    [
        WallsAndObstacles,
        Target
    ],
    [
        WallsAndObstacles,
        ChallengeState,
        Target,
        LapCount
    ],
    ChallengeState
]):
    """Coordinate obstacle-challenge transitions, control, and telemetry.

    The state machine consumes vision results, calculates wall-following and
    obstacle-avoidance corrections, evaluates transitions, and submits the
    command associated with the active state.

    :cvar _DEFAULT_INITIAL_STATE: State used when no initial state is supplied.
    :cvar _DEFAULT_WALL_FOLLOW_KPKD: Proportional and derivative gains for
        wall following.
    :cvar _DEFAULT_CORNER_TURN_KPKD: Gains used during corner turns.
    :cvar _DEFAULT_OBSTACLE_AVOID_KPKD: Gains used during obstacle avoidance.
    :ivar previous_state: State active during the previous update.
    :ivar walls_and_obstacles: Latest vision result.
    :ivar target_position: Latest obstacle target, or ``None``.
    :ivar turn_counter: Number of completed turns.
    :ivar fps: Recent processed-frame rate.
    """
    _DEFAULT_INITIAL_STATE: ChallengeState = "straight"
    _DEFAULT_WALL_FOLLOW_KPKD: tuple[float, float] = GLOBAL_CONFIG(
    ).ObstacleChallengeConfig.WALL_FOLLOW_KPKD
    _DEFAULT_CORNER_TURN_KPKD: tuple[float, float] = GLOBAL_CONFIG(
    ).ObstacleChallengeConfig.CORNER_TURN_KPKD
    _DEFAULT_OBSTACLE_AVOID_KPKD: tuple[float, float] = GLOBAL_CONFIG(
    ).ObstacleChallengeConfig.OBSTACLE_AVOID_KPKD

    _DEFAULT_WALL_FOLLOW_SPEED: float = GLOBAL_CONFIG(
    ).ObstacleChallengeConfig.STRAIGHT_SPEED
    _DEFAULT_CORNER_TURN_SPEED: float = GLOBAL_CONFIG().ObstacleChallengeConfig.TURN_SPEED
    _DEFAULT_OBSTACLE_AVOID_SPEED: float = GLOBAL_CONFIG(
    ).ObstacleChallengeConfig.OBSTACLE_AVOID_SPEED
    _DEFAULT_DRIVE_COMMAND_DURATION: float = GLOBAL_CONFIG(
    ).SharedChallengeConfig.DRIVE_COMMAND_DURATION

    def __init__(
        self,
        initial_state: ChallengeState | None,
        transition_manager: TypedTranisitionManager,
        drive_command_executor: DriveCommandExecutor,
        parallel_parking_state_machine: type[ParallelParkingStateMachine],
        wall_follow_kpkd: tuple[float, float] | None = None,
        corner_turn_kpkd: tuple[float, float] | None = None,
        obstacle_avoid_kpkd: tuple[float, float] | None = None,
        wall_follow_speed: float | None = None,
        corner_turn_speed: float | None = None,
        obstacle_avoid_speed: float | None = None,
        drive_command_duration: float | None = None,
        time_provider: Callable[[], float] = perf_counter,
    ) -> None:
        """Initialize controllers, state, and command defaults.

        :param initial_state: Initial challenge state, or ``None`` to use the
            configured default.
        :param transition_manager: Predicates and priorities used to select
            the next state.
        :param drive_command_executor: Asynchronous command sink.
        :param wall_follow_kpkd: Optional proportional and derivative gains.
        :param corner_turn_kpkd: Optional corner-turn gains.
        :param obstacle_avoid_kpkd: Optional obstacle-avoidance gains.
        :param wall_follow_speed: Optional straight-driving speed.
        :param corner_turn_speed: Optional turning speed.
        :param obstacle_avoid_speed: Optional obstacle-avoidance speed.
        :param drive_command_duration: Optional command duration in seconds.
        :param parallel_parking_state_machine: The state machine for parallel parking.
        :returns: ``None``.
        :rtype: None
        """

        self.wall_follow = (
            PD(*wall_follow_kpkd)
            if wall_follow_kpkd is not None
            else PD(*self._DEFAULT_WALL_FOLLOW_KPKD)
        )
        self.corner_turn = (
            PD(*corner_turn_kpkd)
            if corner_turn_kpkd is not None
            else PD(*self._DEFAULT_CORNER_TURN_KPKD)
        )
        self.obstacle_avoid = (
            PD(*obstacle_avoid_kpkd)
            if obstacle_avoid_kpkd is not None
            else PD(*self._DEFAULT_OBSTACLE_AVOID_KPKD)
        )

        self.wall_follow_speed = (
            wall_follow_speed
            if wall_follow_speed is not None
            else self._DEFAULT_WALL_FOLLOW_SPEED
        )
        self.corner_turn_speed = (
            corner_turn_speed
            if corner_turn_speed is not None
            else self._DEFAULT_CORNER_TURN_SPEED
        )
        self.obstacle_avoid_speed = (
            obstacle_avoid_speed
            if obstacle_avoid_speed is not None
            else self._DEFAULT_OBSTACLE_AVOID_SPEED
        )
        self.drive_command_duration = (
            drive_command_duration
            if drive_command_duration is not None
            else self._DEFAULT_DRIVE_COMMAND_DURATION
        )
        self.round_driving_direction: Literal["CLOCKWISE", "COUNTERCLOCKWISE"] | None = None
        self.time_provider = time_provider

        self.walls_and_obstacles: WallsAndObstacles | None = None
        self.target_position: tuple[int, int] | None = None

        self.wall_error: float = 90.0
        self.turn_correction: float = 90.0
        self.corner_turn_correction: float = 90.0
        self.obstacle_avoidance_correction: float = 90.0

        self.previous_correction: float = 90.0

        self.lap_counter = 0
        self.last_lap_time = self.time_provider() + 20.0  # Seeing the parking lot at the start of the challenge should not count as a lap, so we set this to a value greater than the lap cooldown.

        self._setup_start_time: float | None = None

        self.fps_start_time = self.time_provider()
        self.frame_count = 0  # Frame counter (resets every second)
        self.fps = 0

        self.shm = None
        self.camera_process = None
        self.vision_process = None

        self.parallel_parking_state_machine_type = parallel_parking_state_machine
        self.parallel_parking_state_machine: ParallelParkingStateMachine | None = None

        super().__init__(
            initial_state if initial_state is not None else self._DEFAULT_INITIAL_STATE,
            transition_manager,
            drive_command_executor
        )

    def update(
        self,
        walls_and_obstacles: WallsAndObstacles,
        target_position: tuple[int, int] | None,
    ) -> None:
        """Store vision data, update control corrections, and evaluate a turn.

        :param walls_and_obstacles: Current wall and obstacle measurements.
        :param target_position: Current obstacle target, or ``None``.
        :returns: ``None``.
        :rtype: None
        """
        # calls _populate_transition_params and checks for transitions
        super().update(walls_and_obstacles, target_position)

        # Now state is updated, so we can check to see if we need to update parallel parking state machine
        if self.current_state == "parallel_park" and self.parallel_parking_state_machine is not None:
            self.parallel_parking_state_machine.update(walls_and_obstacles)

 
    def _populate_transition_params(
        self,
        walls_and_obstacles: WallsAndObstacles,
        target_position: tuple[int, int] | None,
    ):
        """Populate the parameters for the transition determinants.

        :param walls_and_obstacles: The current walls and obstacles data.
        :param target_position: The current target position, if any.
        :return: A tuple containing the positional and keyword arguments for the transition determinants.
        """

        self.walls_and_obstacles = walls_and_obstacles
        self.target_position = target_position

        if self.walls_and_obstacles.parking_lot.closer is not None and self.time_provider() - self.last_lap_time > 20.0:
            self.last_lap_time = self.time_provider()
            self.lap_counter += 1

        self.frame_count += 1
        now = self.time_provider()
        if now - self.fps_start_time >= 1.0:
            self.fps = self.frame_count / (now - self.fps_start_time)
            self.frame_count = 0
            self.fps_start_time = now

        self.wall_error = -get_wall_error(walls_and_obstacles)
        self.turn_correction = calculate_EMA(-self.wall_follow.tick(
            self.wall_error) * 90 + 90, self.previous_correction)
        self.corner_turn_correction = calculate_EMA(-self.corner_turn.tick(
            self.wall_error) * 90 + 90, self.previous_correction) - 10 if self.round_driving_direction == "CLOCKWISE" else calculate_EMA(-self.corner_turn.tick(
            self.wall_error) * 90 + 90, self.previous_correction) + 10

        if self.target_position is not None:
            frame_center = GLOBAL_CONFIG().CameraConfig.OUTPUT_WIDTH / 2
            obstacle_error: float = (
                self.target_position[0] - frame_center) / frame_center
            self.obstacle_avoidance_correction = calculate_EMA(
                -self.obstacle_avoid.tick(obstacle_error) * 90 + 90, self.previous_correction)

        kwargs: dict[str, None] = {}

        return (
            walls_and_obstacles,
            self.current_state,
            self.target_position,
            self.lap_counter
        ), kwargs

    def _quick_drive_submit(self, speed: float, correction: float) -> None:
        """Submit a command using the configured challenge duration.

        :param speed: Signed speed for the active state.
        :param correction: Steering correction in servo-angle coordinates.
        :returns: ``None``.
        :rtype: None
        """
        self.drive_command_executor.submit(
            speed,
            correction,
            self.drive_command_duration
        )

    def handle_state_actions(self) -> bool:
        """Execute the command for the active state and detect completion.

        Straight, turning, and obstacle-avoidance states submit their current
        correction. The final state returns ``True`` after its settling delay;
        all other states return ``False``.

        :returns: ``True`` when the obstacle challenge is complete.
        :rtype: bool
        """
        if not self._setup_complete:
            self._setup_complete = self.setup()
            return False

        match self.current_state:
            case "obstacle_avoidance":
                self._quick_drive_submit(
                    self.obstacle_avoid_speed,
                    self.obstacle_avoidance_correction * 0.8 + self.turn_correction * 0.2,
                )
                self.previous_correction = self.obstacle_avoidance_correction * \
                    0.8 + self.turn_correction * 0.2

            case "straight":
                self._quick_drive_submit(
                    self.wall_follow_speed,
                    self.turn_correction
                )
                self.previous_correction = self.turn_correction

            case "turn":
                self._quick_drive_submit(
                    self.corner_turn_speed,
                    self.corner_turn_correction,
                )
                self.previous_correction = self.corner_turn_correction

            case "parallel_park":
                if self.parallel_parking_state_machine is not None:
                    return self.parallel_parking_state_machine.handle_state_actions()
                else:
                    logger.error("Parallel parking state machine is not initialized.")
                    raise RuntimeError("Parallel parking state machine is not initialized."
                    " This should not happen if the transition to parallel parking was triggered correctly.")

        return False  # Return False to indicate that the challenge is not finished yet

    def setup(self) -> bool:
        """
        Exit the parking lot before starting the main loop. This method is called repeatedly until it returns True, indicating that the setup is complete.
        :return: True if the setup is complete and the state machine is ready to proceed, False otherwise.
        """
        if self.round_driving_direction is None:
            self.round_driving_direction =  (
                ("COUNTERCLOCKWISE" if self.walls_and_obstacles.walls.left < self.walls_and_obstacles.walls.right else "CLOCKWISE")
                if self.walls_and_obstacles is not None else None
            ) 

            if self.round_driving_direction is not None:
                self.parallel_parking_state_machine = self.parallel_parking_state_machine_type(
                    drive_command_executor=self.drive_command_executor,
                    round_driving_direction=self.round_driving_direction,
                    time_provider=self.time_provider,
                )

        if not self.round_driving_direction:
            logger.warning("Walls and obstacles data is not available. Cannot determine which side to exit from.")
            return False

        now = self.time_provider()
        if self._setup_start_time is None:
            self._setup_start_time = now
            logger.info("Exiting parking lot...")

        elapsed = now - self._setup_start_time

        if elapsed < 3.0:
            self._quick_drive_submit(
                0.3,
                150 if self.round_driving_direction == "COUNTERCLOCKWISE" else 30,
            )
            return False
        elif elapsed < 5.5:
            self._quick_drive_submit(
                0.3,
                90,
            )
            return False
        elif elapsed < 8.5:
            self._quick_drive_submit(
                -0.3,
                150 if self.round_driving_direction == "COUNTERCLOCKWISE" else 30,
            )
            return False
        elif elapsed < 12:
            self._quick_drive_submit(
                -0.3,
                90,
            )
            return False


        logger.success("Exiting parking lot complete. Starting main loop...")
        return True