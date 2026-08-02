from typing import Literal

from time import perf_counter

from piclient.core.vision import WallsAndObstacles
from piclient.core.lib import TransitionManager, GLOBAL_CONFIG
from piclient.core.lib import export

ChallengeState = Literal[
    "obstacle_avoidance",
    "straight",
    "turn",
    "final_turn",
    "final_straight"
]

TypedTranisitionManager = TransitionManager[
    [
        WallsAndObstacles,
        ChallengeState,
        tuple[int, int] | None,
        float,
        int,
        float | None
    ],
    ChallengeState
]


def is_avoiding_obstacle(walls_and_obstacles: WallsAndObstacles) -> bool:
    """Determine if the robot is currently avoiding an obstacle.

    :param walls_and_obstacles: Walls and obstacles data.
    :returns: True if an obstacle is detected, False otherwise.
    """
    return walls_and_obstacles.obstacles is not None


def is_straight(walls_and_obstacles: WallsAndObstacles) -> bool:
    """Determine if the robot is currently in a straight path.

    :param walls_and_obstacles: Walls and obstacles data.
    :returns: True if no turn is detected, False otherwise.
    """
    return walls_and_obstacles.walls.center <= GLOBAL_CONFIG().SharedChallengeConfig.CENTER_FILL_THRESHOLD


def is_turn(walls_and_obstacles: WallsAndObstacles, last_turn_time: float) -> bool:
    """Determine if a turn is detected based on wall distances.

    :param walls_and_obstacles: Walls and obstacles data.
    :returns: True if a turn is detected, False otherwise.
    """
    return not is_straight(walls_and_obstacles) and perf_counter() - last_turn_time >= GLOBAL_CONFIG().SharedChallengeConfig.TURN_COOLDOWN


@export
def should_avoid_obstacle(
    walls_and_obstacles: WallsAndObstacles,
    state: ChallengeState,
    target: tuple[int, int] | None,
    last_turn_time: float,
    turn_counter: int,
    start_time: float | None,
) -> bool:
    """Transition into obstacle avoidance when the camera target is present."""
    del turn_counter, start_time
    return (
        target is not None
        and (
            state == "turn"
            or (state == "straight" and not is_turn(walls_and_obstacles, last_turn_time))
        )
    )


@export
def should_straight(
    walls_and_obstacles: WallsAndObstacles,
    state: ChallengeState,
    target: tuple[int, int] | None,
    last_turn_time: float,
    turn_counter: int,
    start_time: float | None,
) -> bool:
    """Transition back to straight driving once the obstacle is cleared."""
    del turn_counter, start_time
    return state in {"obstacle_avoidance", "turn"} and target is None and not is_turn(walls_and_obstacles, last_turn_time)


@export
def should_turn(
    walls_and_obstacles: WallsAndObstacles,
    state: ChallengeState,
    target: tuple[int, int] | None,
    last_turn_time: float,
    turn_counter: int,
    start_time: float | None,
) -> bool:
    """Transition into the turn state when a wall corner is detected."""
    del target, turn_counter, start_time
    return state in {"straight", "obstacle_avoidance"} and is_turn(walls_and_obstacles, last_turn_time)


@export
def should_final_turn(
    walls_and_obstacles: WallsAndObstacles,
    state: ChallengeState,
    target: tuple[int, int] | None,
    last_turn_time: float,
    turn_counter: int,
    start_time: float | None,
) -> bool:
    """Transition into the lap-ending final turn."""
    del target, start_time
    return (
        state != "final_turn"
        and turn_counter >= GLOBAL_CONFIG().SharedChallengeConfig.LAP_LENGTH_IN_TURNS
        and is_turn(walls_and_obstacles, last_turn_time)
    )


@export
def should_final_straight(
    walls_and_obstacles: WallsAndObstacles,
    state: ChallengeState,
    target: tuple[int, int] | None,
    last_turn_time: float,
    turn_counter: int,
    start_time: float | None,
) -> bool:
    """Transition from the final turn to the finishing straight."""
    del target, turn_counter, start_time
    return (
        state == "final_turn"
        and is_straight(walls_and_obstacles)
    )
