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
    "final_straight_and_parking"
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
    """Return whether the most recent vision sample indicates obstacle avoidance is active.

    This helper is used by the challenge state machine to decide if the robot is
    currently avoiding a detected obstacle in the path ahead. The result is
    computed from the obstacle payload in the latest :class:`WallsAndObstacles`
    sample rather than from the current state label.

    :param walls_and_obstacles: The latest :class:`WallsAndObstacles` sample
        produced by the vision pipeline, including obstacle and wall geometry.
    :returns: ``True`` when an obstacle is present, otherwise ``False``.
    :rtype: bool
    """
    return walls_and_obstacles.obstacles is not None


def is_straight(walls_and_obstacles: WallsAndObstacles) -> bool:
    """Return whether the current wall geometry suggests the robot is in a straight segment.

    The decision uses the center wall fill ratio from the current vision frame. A
    low ratio indicates the corridor is open and the robot can continue straight,
    while a larger ratio indicates that a turn or corner is being approached.

    :param walls_and_obstacles: The most recent :class:`WallsAndObstacles`
        data containing the center-wall fill information.
    :returns: ``True`` when the center wall fill is below the configured straight
        threshold, otherwise ``False``.
    :rtype: bool
    """
    return walls_and_obstacles.walls.center <= GLOBAL_CONFIG().SharedChallengeConfig.CENTER_FILL_THRESHOLD


def is_turn(walls_and_obstacles: WallsAndObstacles, last_turn_time: float) -> bool:
    """Return whether a turn is currently considered active, with cooldown enforcement.

    This helper combines the straight-path check with a cooldown timer so the
    challenge does not repeatedly trigger turn transitions from the same wall
    geometry over a short period of time.

    :param walls_and_obstacles: The latest :class:`WallsAndObstacles` sample
        used to evaluate the corridor geometry.
    :param last_turn_time: Monotonic timestamp captured when the previous turn
        transition was last triggered.
    :returns: ``True`` only when the robot is not in a straight corridor and the
        cooldown period has elapsed, otherwise ``False``.
    :rtype: bool
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
    """Decide whether the robot should transition into obstacle avoidance.

    This rule is triggered when a visible target is present while the robot is in
    a turn or while it is driving straight but the wall geometry does not yet
    indicate a valid turn. It is the decision point that moves the challenge from
    normal wall-following into the obstacle-avoidance state.

    :param walls_and_obstacles: The latest :class:`WallsAndObstacles` sample
        containing the wall and obstacle geometry used to evaluate the state.
    :param state: The active challenge state, such as ``"straight"`` or
        ``"turn"``.
    :param target: Detector output for the visible obstacle target, or
        ``None`` when no target is currently visible.
    :param last_turn_time: Monotonic timestamp for the most recent turn event.
    :param turn_counter: Number of completed turns; this parameter is unused by
        this rule.
    :param start_time: Challenge start timestamp; this parameter is unused by
        this rule.
    :returns: ``True`` when obstacle avoidance should be selected, otherwise
        ``False``.
    :rtype: bool
    """
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
    """Check whether the robot should return to the straight-driving state.

    The rule allows the robot to resume regular wall-following once an obstacle
    is cleared and no turn is active. It is primarily used after obstacle
    avoidance or during a turn when the wall geometry is clear.

    :param walls_and_obstacles: The most recent :class:`WallsAndObstacles`
        measurement containing wall and obstacle data.
    :param state: The current state of the challenge state machine.
    :param target: The current target coordinates, or ``None`` when no obstacle
        target is visible.
    :param last_turn_time: Time of the most recent turn transition.
    :param turn_counter: Number of completed turns; this parameter is unused.
    :param start_time: Start time of the challenge; this parameter is unused.
    :returns: ``True`` when the robot should drive straight again, otherwise
        ``False``.
    :rtype: bool
    """
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
    """Decide whether the wall geometry requires a turn transition.

    This predicate is used when the robot should leave the straight path and
    begin following the corner geometry. It checks the current wall fill against
    the turn cooldown so the transition is only triggered after a sustained turn
    condition.

    :param walls_and_obstacles: The current :class:`WallsAndObstacles` sample.
    :param state: The active challenge state.
    :param target: Target coordinates from the vision system; this parameter is
        unused by this rule.
    :param last_turn_time: Timestamp of the last turn event used for cooldown.
    :param turn_counter: Number of completed turns; this parameter is unused.
    :param start_time: Challenge start timestamp; this parameter is unused.
    :returns: ``True`` when the robot should transition into the turn state,
        otherwise ``False``.
    :rtype: bool
    """
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
    """Decide when the challenge should enter the final-turn phase.

    Once the robot has completed the configured number of turns for the lap, the
    final turn is triggered when the wall geometry still indicates a valid turn.
    This keeps the challenge progression aligned with the lap-length target.

    :param walls_and_obstacles: The latest :class:`WallsAndObstacles` sample
        used to evaluate the corridor geometry.
    :param state: Current state within the challenge state machine.
    :param target: Target coordinates from vision; this parameter is unused.
    :param last_turn_time: Monotonic timestamp for the previous turn event.
    :param turn_counter: Number of turns completed so far.
    :param start_time: Challenge start time; this parameter is unused.
    :returns: ``True`` when the lap-turn count has been reached and a turn is
        detected, otherwise ``False``.
    :rtype: bool
    """
    del target, start_time
    return (
        state != "final_turn"
        and turn_counter >= GLOBAL_CONFIG().SharedChallengeConfig.LAP_LENGTH_IN_TURNS
        and is_turn(walls_and_obstacles, last_turn_time)
    )


@export
def should_final_straight_and_parking(
    walls_and_obstacles: WallsAndObstacles,
    state: ChallengeState,
    target: tuple[int, int] | None,
    last_turn_time: float,
    turn_counter: int,
    start_time: float | None,
) -> bool:
    """Return whether the final turn has reached the finishing straight.

    When the robot is already in the final-turn state and the wall geometry
    indicates a straight corridor, the challenge can advance to the final straight
    and parking phase. This is the transition that ends the corner-following
    behavior and prepares for the final maneuver.

    :param walls_and_obstacles: The current :class:`WallsAndObstacles` sample.
    :param state: Active challenge state.
    :param target: Target coordinates from the vision system; this parameter is
        unused.
    :param last_turn_time: Timestamp of the last turn event; this parameter is
        unused in this rule.
    :param turn_counter: Completion count for prior turns; unused here.
    :param start_time: Challenge start timestamp; unused here.
    :returns: ``True`` when the robot is in the final-turn state and the corridor
        is straight, otherwise ``False``.
    :rtype: bool
    """
    del target, turn_counter, start_time
    return (
        state == "final_turn"
        and is_straight(walls_and_obstacles)
    )
