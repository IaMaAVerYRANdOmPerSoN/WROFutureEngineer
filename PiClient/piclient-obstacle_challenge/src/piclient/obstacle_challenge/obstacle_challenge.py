"""
Obstacle Challenge main loop class
Extends StateMachine to implement the main loop for the Obstacle Challenge.
"""
# TODO: Create StateMachine class in piclient-core and port the logic from runner.py to here.

from time import perf_counter

from numpy import isfinite

from loguru import logger
from piclient.core.interface import DriveCommandExecutor
from piclient.core.lib import PD, StateMachine, GLOBAL_CONFIG
from piclient.core.vision import WallsAndObstacles

from .transition_determinants import (
    TypedTranisitionManager,
    ChallengeState,
)


def get_wall_error(walls_and_obstacles: WallsAndObstacles) -> float:
    """Return the wall-following error as a finite scalar."""
    left_distance = float(walls_and_obstacles.walls.left)
    right_distance = float(walls_and_obstacles.walls.right)

    if not isfinite(left_distance):
        left_distance = 1.0
    if not isfinite(right_distance):
        right_distance = 1.0

    return right_distance - left_distance


def calculate_EMA(latest: float, accumulated: float | None, alpha: float =0.5) -> float:
    """Calculate the Exponential Moving Average of a series of values."""
    if accumulated is None:
        return latest
    return alpha * latest + (1 - alpha) * accumulated


class ObstacleChallengeStateMachine(StateMachine[
    [],
    [
        WallsAndObstacles,
        tuple[int, int] | None
    ],
    [
        WallsAndObstacles,
        ChallengeState,
        tuple[int, int] | None,
        float,
        int,
        float | None
    ],
    ChallengeState
]):
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
        wall_follow_kpkd: tuple[float, float] | None = None,
        corner_turn_kpkd: tuple[float, float] | None = None,
        obstacle_avoid_kpkd: tuple[float, float] | None = None,
        wall_follow_speed: float | None = None,
        corner_turn_speed: float | None = None,
        obstacle_avoid_speed: float | None = None,
        drive_command_duration: float | None = None
    ) -> None:

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

        self.previous_state: ChallengeState | None = None

        self.walls_and_obstacles: WallsAndObstacles | None = None
        self.target_position: tuple[int, int] | None = None

        self.wall_error: float = 90.0
        self.turn_correction: float = 90.0
        self.corner_turn_correction: float = 90.0
        self.obstacle_avoidance_correction: float = 90.0

        self.previous_turn_correction: float = 90.0
        self.previous_corner_turn_correction: float = 90.0
        self.previous_obstacle_avoidance_correction: float = 90.0

        self.turn_counter = 0
        self.start_time = None  # Start time for the final straight
        self.last_turn_time = 0  # Time of the last detected turn

        self.fps_start_time = perf_counter()
        self.frame_count = 0  # Frame counter (resets every second)
        self.fps = 0

        self.shm = None
        self.camera_process = None
        self.vision_process = None

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
        # calls _populate_transition_params and checks for transitions
        super().update(walls_and_obstacles, target_position)

        if self.current_state == "final_straight" and self.start_time is None:
            self.start_time = perf_counter()

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

        self.frame_count += 1
        now = perf_counter()
        if now - self.fps_start_time >= 1.0:
            self.fps = self.frame_count / (now - self.fps_start_time)
            self.frame_count = 0
            self.fps_start_time = now

        self.wall_error = get_wall_error(walls_and_obstacles)
        self.turn_correction = calculate_EMA(self.wall_follow.tick(self.wall_error) * 90 + 90, self.previous_turn_correction)
        self.corner_turn_correction = calculate_EMA(self.corner_turn.tick(self.wall_error) * 90 + 90, self.previous_corner_turn_correction)
        self.previous_turn_correction = self.turn_correction
        self.previous_corner_turn_correction = self.corner_turn_correction

        if self.target_position is not None:
            frame_center = GLOBAL_CONFIG().CameraConfig.OUTPUT_WIDTH / 2
            obstacle_error = (
                self.target_position[0] - frame_center) / frame_center
            self.obstacle_avoidance_correction = calculate_EMA(self.obstacle_avoid.tick(obstacle_error) * 90 + 90, self.previous_obstacle_avoidance_correction)
            self.previous_obstacle_avoidance_correction = self.obstacle_avoidance_correction
        else:
            self.obstacle_avoidance_correction = 90.0
            self.previous_obstacle_avoidance_correction = 90.0

        if (
            self.previous_state == "turn"
            and self.current_state != "turn"
            and perf_counter() - self.last_turn_time >= GLOBAL_CONFIG().SharedChallengeConfig.TURN_COOLDOWN
        ):
            self.last_turn_time = perf_counter()
            self.turn_counter += 1
        
        self.previous_state = self.current_state

        kwargs: dict[str, None] = {}

        return (
            walls_and_obstacles,
            self.current_state,
            self.target_position,
            self.last_turn_time,
            self.turn_counter,
            self.start_time
        ), kwargs

    def _quick_drive_submit(self, speed: float, correction: float) -> None:
        self.drive_command_executor.submit(
            speed,
            correction,
            self.drive_command_duration
        )

    def handle_state_actions(self) -> bool:
        match self.current_state:
            case "obstacle_avoidance":
                if self.target_position is not None:  # 1st priority is to avoid obstacles
                    self._quick_drive_submit(
                        self.obstacle_avoid_speed,
                        self.obstacle_avoidance_correction,
                    )

            case "straight":
                self._quick_drive_submit(
                    self.wall_follow_speed,
                    self.turn_correction,
                )

            case "turn":
                self._quick_drive_submit(
                    self.corner_turn_speed,
                    self.corner_turn_correction,
                )

            case "final_turn":
                self._quick_drive_submit(
                    self.corner_turn_speed,
                    self.corner_turn_correction,
                )

            case "final_straight":
                self.start_time = perf_counter() if not self.start_time else self.start_time
                now = perf_counter()

                if now - self.start_time > 0.5:
                    logger.success("Finished!")
                    return True  # Return True to indicate that the challenge is finished

                self._quick_drive_submit(
                    self.wall_follow_speed,
                    self.turn_correction,
                )

            case _:
                logger.error(f"Unrecognized state: {state}")
                state = "straight"  # Reset to a safe state

        return False  # Return False to indicate that the challenge is not finished yet
